#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebPForge —— 批量图片转 WebP 工具
=================================

一个跨平台(Windows / macOS)的图片批量转换工具, 同时支持两种使用方式:

1. 图形界面 (双击运行)
      双击 WebPForge.exe   (Windows)
      双击 WebPForge.app   (macOS)
   在界面里添加图片/文件夹, 选择质量, 点击"开始转换"即可。

2. 命令行 (可选, 便于批处理脚本调用)
      WebPForge --cli -i "D:/photos" -o "D:/out" -q 80

项目主页: https://github.com/K-zhaochao/WebPForge
许可: MIT
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import queue
import tempfile
import traceback
import time
import json
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from pathlib import Path

# ----------------------------------------------------------------------------
# 基础常量
# ----------------------------------------------------------------------------

APP_NAME = "WebPForge"
APP_TITLE = f"{APP_NAME} · 批量图片格式转换"
APP_VERSION = "1.0.0"
REPO_URL = "https://github.com/K-zhaochao/WebPForge"


def open_in_browser(url: str) -> None:
    """在系统默认浏览器里打开链接(界面里的"项目主页"按钮用)。"""
    try:
        import webbrowser
        webbrowser.open(url, new=2)
    except Exception:
        pass

# 可读入的源格式 (Pillow 支持的常见格式)
READ_EXTS = {
    ".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".bmp", ".gif", ".tif", ".tiff",
    ".webp", ".ico", ".tga", ".ppm", ".pgm", ".pbm", ".pnm", ".dds", ".jp2",
    ".j2k", ".pcx", ".avif", ".heic", ".heif", ".psd", ".eps", ".svg", ".cr2",
    ".nef", ".dng", ".arw", ".raf", ".orf", ".rw2", ".srw", ".pef",
}

# 输出格式
OUT_FORMATS = {
    "WebP (.webp)": ("webp", ".webp"),
    "PNG (.png)": ("png", ".png"),
    "JPEG (.jpg)": ("jpeg", ".jpg"),
    "AVIF (.avif)": ("avif", ".avif"),
}

# 体积单位
_UNITS = ("B", "KB", "MB", "GB")


def human_size(num: float) -> str:
    """把字节数转成人看的字符串。"""
    if num is None:
        return "-"
    num = float(num)
    neg = num < 0
    num = abs(num)
    for unit in _UNITS:
        if num < 1024 or unit == _UNITS[-1]:
            txt = f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
            return ("-" if neg else "") + txt
        num /= 1024.0
    return f"{num:.1f} GB"


def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in READ_EXTS


# ----------------------------------------------------------------------------
# 输出文件名分配
#
# 注意: 转换是多线程并发的, 两个源文件(例如 anim.webp 和 anim(1).webp)可能
# 映射到同一个目标名。仅靠"检查磁盘上是否存在"会漏掉"已被其他线程预定、但
# 尚未落盘"的名字, 因此这里用一把进程级锁 + 已预定集合来保证全局唯一。
# ----------------------------------------------------------------------------

_NAME_LOCK = threading.RLock()
_RESERVED: set[str] = set()


def _key(path: Path) -> str:
    try:
        return os.path.normcase(str(path.resolve()))
    except OSError:
        return os.path.normcase(os.path.abspath(str(path)))


def _output_key(path: Path) -> str:
    key = _key(path)
    # macOS 默认 APFS 卷不区分大小写；保守避让大小写冲突，扫描去重不受影响。
    return key.casefold() if sys.platform == "darwin" else key


def reserve_unique_path(path: Path, overwrite: bool = False,
                        protected: set[str] | None = None,
                        owner: set[str] | None = None) -> Path:
    """在并发环境下为 path 分配一个唯一的输出文件名。

    默认 name.webp -> name(1).webp -> name(2).webp；覆盖仅允许原始目标名。
    """
    with _NAME_LOCK:
        stem, suffix, parent = path.stem, path.suffix, path.parent
        cand = path
        i = 0
        while True:
            k = _output_key(cand)
            can_replace = overwrite and i == 0 and not cand.is_dir()
            if (k not in _RESERVED and k not in (protected or ())
                    and (can_replace or not os.path.lexists(cand))):
                _RESERVED.add(k)
                if owner is not None:
                    owner.add(k)
                return cand
            i += 1
            if i > 100000:
                raise OSError(f"无法为 {path} 找到可用的文件名")
            cand = parent / f"{stem}({i}){suffix}"


def release_reserved_path(path: Path) -> None:
    """转换失败时释放预定, 让后续任务可以复用这个名字。"""
    with _NAME_LOCK:
        _RESERVED.discard(_output_key(path))


class _OutputPaths:
    """一次批处理的文件名预留；保护全部输入，结束后统一释放。"""

    def __init__(self, sources):
        self.protected = {_output_key(src) for src in sources}
        self.keys: set[str] = set()

    def reserve(self, path: Path, overwrite: bool) -> Path:
        return reserve_unique_path(path, overwrite, self.protected, self.keys)

    def close(self) -> None:
        # 用预留时的 key：替换符号链接后 resolve() 的结果可能已经改变。
        with _NAME_LOCK:
            _RESERVED.difference_update(self.keys)
            self.keys.clear()


def _publish_without_overwrite(tmp: Path, dst: Path) -> None:
    """原子发布；其他进程抢先创建目标文件时也不覆盖。"""
    if os.name == "nt":
        os.rename(tmp, dst)  # Windows 的 rename 在目标已存在时失败
    else:
        os.link(tmp, dst)    # 同目录硬链接：POSIX 下原子且不会替换目标
        tmp.unlink()


def _publish_output(tmp: Path, target: Path, overwrite: bool,
                    paths: _OutputPaths) -> Path:
    # Windows 旧版 Python 的路径检查会短暂占用目标文件。命名检查与发布
    # 共用锁，避免其他工作线程的检查阻止原子替换；图片编码仍然并行。
    with _NAME_LOCK:
        while True:
            dst = paths.reserve(target, overwrite)
            if overwrite and dst == target:
                os.replace(tmp, dst)
                return dst
            try:
                _publish_without_overwrite(tmp, dst)
                return dst
            except FileExistsError:
                # 编码期间外部程序可能创建同名文件，重新分配名字再发布。
                continue


# ----------------------------------------------------------------------------
# 转换参数
# ----------------------------------------------------------------------------

@dataclass
class Options:
    quality: int = 80
    lossless: bool = False
    out_fmt: str = "webp"          # webp / png / jpeg / avif
    out_ext: str = ".webp"
    keep_structure: bool = False   # 保留子文件夹结构
    overwrite: bool = False        # 覆盖同名文件
    flatten: bool = False          # 透明区域填充背景色(而不是保留透明)
    bg: str = "#ffffff"            # 填充色
    max_edge: int = 0              # 限制最长边像素, 0 = 不缩放
    also_smaller_only: bool = False  # 仅当结果更小才写盘
    workers: int = 0               # 线程数, 0 = 自动
    recursive: bool = True


@dataclass
class Item:
    src: Path
    rel: str = ""            # 相对于扫描根目录的路径(用于保留结构)
    status: str = "等待"      # 等待 / 转换中 / 完成 / 跳过 / 失败 / 已取消
    dst: str = ""
    src_size: int = 0
    dst_size: int = 0
    message: str = ""


@dataclass
class Result:
    ok: int = 0
    skipped: int = 0
    failed: int = 0
    cancelled: int = 0
    src_bytes: int = 0
    dst_bytes: int = 0
    elapsed: float = 0.0
    errors: list[tuple[str, str]] = field(default_factory=list)


# ----------------------------------------------------------------------------
# 核心转换
# ----------------------------------------------------------------------------

def _pil():
    """延迟导入 Pillow, 这样 GUI 可以先弹出来。"""
    from PIL import Image, ImageOps  # noqa
    return Image, ImageOps


def _flatten_color(Image, bg: str):
    with Image.new("RGB", (1, 1), bg) as sample:
        return sample.getpixel((0, 0))


def validate_options(opts: Options) -> None:
    """GUI、CLI 与批处理共用校验，错误设置在转换前报告。"""
    if opts.out_fmt not in ("webp", "png", "jpeg", "avif"):
        raise ValueError("不支持的输出格式")
    if not 1 <= opts.quality <= 100:
        raise ValueError("质量必须在 1–100 之间")
    if opts.max_edge < 0:
        raise ValueError("最长边必须为非负整数，0 表示不缩放")
    if opts.workers < 0:
        raise ValueError("线程数必须为非负整数，0 表示自动")
    if opts.lossless and opts.out_fmt not in ("webp", "png"):
        raise ValueError("无损模式仅支持 WebP 和 PNG，请更换格式或关闭无损模式")
    Image, _ = _pil()
    try:
        _flatten_color(Image, opts.bg)
    except (ValueError, TypeError) as exc:
        raise ValueError("背景色无效，请填写 #ffffff 这样的颜色值") from exc
    Image.init()
    if opts.out_fmt.upper() not in Image.SAVE:
        raise ValueError(f"当前 Pillow 不支持 {opts.out_fmt.upper()} 编码，请升级 Pillow")


def resolve_target_dir(item: Item, opts: Options, out_root: Path | None) -> Path:
    """None 表示原图旁边；显式指定的 '.' 表示当前工作目录。"""
    if out_root is None:
        return item.src.parent
    if opts.keep_structure and item.rel and item.rel != ".":
        relative = Path(item.rel)
        if relative.is_absolute() or relative.drive or ".." in relative.parts:
            raise ValueError("子文件夹路径必须位于输出目录内")
        return out_root / relative
    return out_root


class _ConversionCancelled(Exception):
    pass


def _check_cancelled(should_stop) -> None:
    if should_stop and should_stop():
        raise _ConversionCancelled()


def _cancel_item(item: Item) -> Item:
    item.status = "已取消"
    item.dst = ""
    item.dst_size = 0
    item.message = "已取消，可再次开始转换"
    return item


def _prepare_image(im, opts: Options, Image, ImageOps):
    """统一处理方向、缩放和透明度，供单帧和动画使用。"""
    image = ImageOps.exif_transpose(im)
    try:
        if opts.max_edge:
            image.thumbnail((opts.max_edge, opts.max_edge), Image.LANCZOS)
        has_alpha = image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info
        if (opts.flatten or opts.out_fmt == "jpeg") and has_alpha:
            metadata = dict(image.info)
            metadata.pop("transparency", None)
            with image.convert("RGBA") as rgba:
                canvas = Image.new("RGB", image.size, _flatten_color(Image, opts.bg))
                with rgba.getchannel("A") as alpha:
                    canvas.paste(rgba, mask=alpha)
                canvas.info.update(metadata)
            image.close()
            image = canvas
        if opts.out_fmt == "jpeg" and image.mode not in ("RGB", "L"):
            converted = image.convert("RGB")
            image.close()
            image = converted
        elif opts.out_fmt == "png" and image.mode not in ("1", "L", "LA", "I", "I;16", "RGB", "RGBA"):
            converted = image.convert("RGBA" if has_alpha and not opts.flatten else "RGB")
            image.close()
            image = converted
        return image
    except Exception:
        image.close()
        raise


def convert_one(item: Item, opts: Options, out_root: Path | None, *,
                should_stop=None, output_paths: _OutputPaths | None = None) -> Item:
    """转换单张图片；失败或取消不留下输出，也不保留上次的结果字段。"""
    own_paths = output_paths is None
    paths = output_paths
    tmp_dst = None
    frames = []
    item.status, item.dst, item.dst_size, item.message = "转换中", "", 0, ""
    try:
        _check_cancelled(should_stop)
        if own_paths:
            validate_options(opts)
            paths = _OutputPaths([item.src])
        Image, ImageOps = _pil()
        item.src_size = item.src.stat().st_size
        target_dir = resolve_target_dir(item, opts, out_root)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / (item.src.stem + opts.out_ext)

        with Image.open(item.src) as im:
            im.load()
            n_frames = int(getattr(im, "n_frames", 1) or 1)
            animated = n_frames > 1 and opts.out_fmt == "webp"
            # GIF 没有循环扩展时只播放一次；不能默认为无限循环。
            loop = int(im.info.get("loop", 1))
            durations = []
            for index in range(n_frames if animated else 1):
                _check_cancelled(should_stop)
                im.seek(index)
                frames.append(_prepare_image(im, opts, Image, ImageOps))
                durations.append(max(0, int(im.info.get("duration", 100))))

            first = frames[0]
            kwargs = {}
            for metadata in ("icc_profile", "exif"):
                if first.info.get(metadata):
                    kwargs[metadata] = first.info[metadata]
            if opts.out_fmt == "webp":
                kwargs.update(lossless=opts.lossless, quality=opts.quality,
                              method=6, exact=opts.lossless)
                if animated:
                    kwargs.update(save_all=True, append_images=frames[1:],
                                  duration=durations, loop=loop)
            elif opts.out_fmt == "jpeg":
                kwargs.update(quality=opts.quality, optimize=True, progressive=True,
                              subsampling=0 if opts.quality >= 90 else 2)
            elif opts.out_fmt == "png":
                kwargs["optimize"] = True
                if not opts.lossless and opts.quality < 100 and first.mode in ("RGB", "RGBA", "L", "LA"):
                    colors = 256 if opts.quality >= 75 else max(8, int(256 * opts.quality / 100))
                    if first.mode == "LA":
                        converted = first.convert("RGBA")
                        first.close()
                        first = frames[0] = converted
                    method = Image.FASTOCTREE if first.mode == "RGBA" else Image.MEDIANCUT
                    quantized = first.quantize(colors=colors, method=method)
                    first.close()
                    first = frames[0] = quantized
            elif opts.out_fmt == "avif":
                # 每个转换任务只使用一个 AVIF 编码线程，避免批量时嵌套并发。
                kwargs.update(quality=opts.quality, max_threads=1)

            _check_cancelled(should_stop)
            fd, name = tempfile.mkstemp(prefix=".wc_tmp_", suffix=opts.out_ext,
                                       dir=str(target_dir))
            os.close(fd)
            tmp_dst = Path(name)
            first.save(tmp_dst, format=opts.out_fmt.upper(), **kwargs)

        _check_cancelled(should_stop)
        new_size = tmp_dst.stat().st_size
        if opts.also_smaller_only and item.src_size and new_size >= item.src_size:
            item.status = "跳过"
            item.dst_size = item.src_size
            item.message = f"原文件更小或相同({human_size(item.src_size)}), 已保留原图"
            return item

        dst = _publish_output(tmp_dst, target, opts.overwrite, paths)
        item.dst = str(dst)
        item.dst_size = new_size
        item.status = "完成"
        ratio = f" ({(new_size - item.src_size) / item.src_size * 100:+.0f}%)" if item.src_size else ""
        item.message = f"{human_size(item.src_size)} → {human_size(new_size)}{ratio}"
        if animated:
            item.message += f" · 动画 {len(frames)} 帧"
        elif n_frames > 1:
            item.message += " · 当前输出格式仅保留首帧"
        return item
    except _ConversionCancelled:
        return _cancel_item(item)
    except Exception as exc:
        item.status = "失败"
        item.message = f"{type(exc).__name__}: {exc}"
        return item
    finally:
        for frame in frames:
            frame.close()
        if tmp_dst is not None:
            try:
                tmp_dst.unlink(missing_ok=True)
            except OSError:
                pass
        if own_paths and paths is not None:
            paths.close()


def collect_files(inputs: list[Path], recursive: bool = True, *,
                  should_stop=None, exclude_dirs=()) -> list[Item]:
    """把输入(文件或文件夹)展开成待转换图片列表, 自动去重。"""
    items: list[Item] = []
    seen: set[str] = set()
    excluded = {_key(Path(path)) for path in exclude_dirs}

    def add(p: Path, rel: str):
        key = _key(p)
        if key in seen:
            return
        seen.add(key)
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        items.append(Item(src=p, rel=rel, src_size=size))

    for raw in inputs:
        if should_stop and should_stop():
            break
        p = Path(raw)
        if p.is_dir():
            for directory, subdirs, filenames in os.walk(p):
                if should_stop and should_stop():
                    break
                base = Path(directory)
                subdirs[:] = sorted(d for d in subdirs if recursive and _key(base / d) not in excluded)
                rel = str(base.relative_to(p))
                for name in sorted(filenames):
                    if should_stop and should_stop():
                        break
                    f = base / name
                    if is_image_file(f) and f.is_file():
                        add(f, "" if rel == "." else rel)
        elif p.is_file():
            add(p, "")
        elif not p.exists():
            # 允许通配符
            import glob as _glob
            for g in _glob.iglob(str(raw), recursive=recursive):
                if should_stop and should_stop():
                    break
                gp = Path(g)
                if gp.is_file() and is_image_file(gp):
                    add(gp, "")
    return items


def load_preview(path: Path, bounds=(1000, 1000)):
    """只解码一次并缓存缩略图；手机照片预览与实际转换方向一致。"""
    Image, ImageOps = _pil()
    with Image.open(path) as original:
        size = original.size
        if original.getexif().get(0x0112) in (5, 6, 7, 8):
            size = size[::-1]
        original.draft("RGB", bounds)
        thumb = ImageOps.exif_transpose(original)
        try:
            thumb.thumbnail(bounds, Image.LANCZOS)
            if thumb.mode not in ("RGB", "RGBA", "L") or "transparency" in thumb.info:
                converted = thumb.convert("RGBA")
                thumb.close()
                thumb = converted
            return thumb, size
        except Exception:
            thumb.close()
            raise


def run_batch(items: list[Item], opts: Options, out_root: Path | None,
              progress=None, should_stop=None) -> Result:
    """按完成顺序报告结果，同时在途任务不超过线程数；取消后不再提交新任务。"""
    validate_options(opts)
    res = Result()
    total = len(items)
    if total == 0:
        return res

    workers = min(opts.workers or min(8, os.cpu_count() or 4), total)
    done = 0
    next_index = 0
    t0 = time.monotonic()
    paths = _OutputPaths(it.src for it in items)

    def stopped():
        return bool(should_stop and should_stop())

    def report(it: Item):
        nonlocal done
        done += 1
        if it.status == "完成":
            res.ok += 1
            res.src_bytes += it.src_size
            res.dst_bytes += it.dst_size
        elif it.status == "跳过":
            res.skipped += 1
            res.src_bytes += it.src_size
            res.dst_bytes += it.src_size
        elif it.status == "已取消":
            res.cancelled += 1
        else:
            res.failed += 1
            res.errors.append((str(it.src), it.message))
        if progress:
            try:
                progress(done, total, it)
            except Exception:
                pass

    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            pending = {}

            def fill_workers():
                nonlocal next_index
                while next_index < total and len(pending) < workers and not stopped():
                    item = items[next_index]
                    next_index += 1
                    future = pool.submit(convert_one, item, opts, out_root,
                                         should_stop=should_stop, output_paths=paths)
                    pending[future] = item

            fill_workers()
            while pending:
                finished, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in finished:
                    item = pending.pop(future)
                    try:
                        item = future.result()
                    except Exception as exc:
                        # 即使某个工作线程抛出意外异常，也继续收集其他文件的结果。
                        item.status, item.dst, item.dst_size = "失败", "", 0
                        item.message = f"{type(exc).__name__}: {exc}"
                    report(item)
                fill_workers()

            for item in items[next_index:]:
                report(_cancel_item(item))
    finally:
        paths.close()
        res.elapsed = time.monotonic() - t0
    return res


# ----------------------------------------------------------------------------
# 拖拽支持 (Windows)
# ----------------------------------------------------------------------------

# 必须保存这些引用, 否则 ctypes 回调对象被回收后会导致进程崩溃
_DROP_KEEPALIVE: list = []


def enable_windows_drop(tk_root, callback) -> bool:
    """用 Win32 的 WM_DROPFILES 给窗口加上"把文件拖进来"的能力。

    注意: 这里刻意只处理 Windows 原生消息, 且回调内部全部包在 try/except 里,
    任何异常都不会影响主程序 —— 拖拽只是锦上添花, 不能让界面崩掉。
    """
    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        shell32 = ctypes.windll.shell32

        # 关键: 显式声明 64 位安全的函数签名, 否则指针会被截断成 32 位
        user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
        user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
        user32.CallWindowProcW.restype = ctypes.c_ssize_t
        user32.CallWindowProcW.argtypes = [ctypes.c_ssize_t, wintypes.HWND,
                                           ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM]
        user32.GetAncestor.restype = wintypes.HWND
        user32.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
        shell32.DragQueryFileW.restype = ctypes.c_uint
        shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, ctypes.c_uint,
                                           wintypes.LPWSTR, ctypes.c_uint]
        shell32.DragFinish.argtypes = [wintypes.HANDLE]

        tk_root.update_idletasks()
        hwnd = user32.GetAncestor(tk_root.winfo_id(), 2) or tk_root.winfo_id()  # GA_ROOT
        if not hwnd:
            return False

        GWL_EXSTYLE = -20
        GWL_WNDPROC = -4
        WS_EX_ACCEPTFILES = 0x00000010
        WM_DROPFILES = 0x0233

        style = user32.GetWindowLongPtrW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style | WS_EX_ACCEPTFILES)
        shell32.DragAcceptFiles(hwnd, True)

        WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, ctypes.c_uint,
                                     wintypes.WPARAM, wintypes.LPARAM)

        def _deliver(files):
            try:
                callback(files)
            except Exception:
                pass

        def _drop_handler(h, msg, wparam, lparam):
            try:
                if msg == WM_DROPFILES:
                    files = _read_drop_files(wparam)
                    if files:
                        tk_root.after(0, lambda f=files: _deliver(f))
                    return 0
            except Exception:
                pass
            return user32.CallWindowProcW(_DROP_KEEPALIVE[1], h, msg, wparam, lparam)

        old_proc = user32.GetWindowLongPtrW(hwnd, GWL_WNDPROC)
        if not old_proc:
            return False
        new_proc = WNDPROC(_drop_handler)
        _DROP_KEEPALIVE[:] = [new_proc, old_proc, _drop_handler, hwnd]

        if not user32.SetWindowLongPtrW(hwnd, GWL_WNDPROC,
                                        ctypes.cast(new_proc, ctypes.c_void_p).value):
            return False
        return True
    except Exception:
        return False


def _read_drop_files(hdrop) -> list[str]:
    """取出拖放事件里的文件路径列表。"""
    import ctypes
    shell32 = ctypes.windll.shell32
    out: list[str] = []
    try:
        count = shell32.DragQueryFileW(hdrop, 0xFFFFFFFF, None, 0)
        buf = ctypes.create_unicode_buffer(32768)
        for i in range(int(count)):
            if shell32.DragQueryFileW(hdrop, i, buf, 32768):
                out.append(buf.value)
    except Exception:
        pass
    finally:
        try:
            shell32.DragFinish(hdrop)
        except Exception:
            pass
    return out


# ----------------------------------------------------------------------------
# 图形界面
# ----------------------------------------------------------------------------

def enable_dpi_awareness() -> None:
    """Windows 高分屏下让界面清晰不模糊(必须在创建窗口前调用)。"""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        # 2 = PROCESS_PER_MONITOR_DPI_AWARE
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def launch_gui() -> int:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    enable_dpi_awareness()

    try:
        from PIL import Image, ImageTk  # noqa
    except Exception:
        Image = ImageTk = None  # type: ignore

    root = tk.Tk()
    root.title(f"{APP_TITLE}  v{APP_VERSION}")
    root.geometry("1120x760")
    root.minsize(940, 620)

    # ---------- 状态变量 ----------
    var_quality = tk.IntVar(value=80)
    var_lossless = tk.BooleanVar(value=False)
    var_fmt = tk.StringVar(value="WebP (.webp)")
    var_outmode = tk.StringVar(value="same")     # same | custom
    var_outdir = tk.StringVar(value="")
    var_keep = tk.BooleanVar(value=False)
    var_overwrite = tk.BooleanVar(value=False)
    var_flatten = tk.BooleanVar(value=False)
    var_bg = tk.StringVar(value="#ffffff")
    var_maxedge = tk.StringVar(value="0")
    var_recursive = tk.BooleanVar(value=True)
    var_smaller_only = tk.BooleanVar(value=True)
    var_status = tk.StringVar(value="就绪 · 把图片或文件夹拖进窗口，然后点「开始转换」")
    var_progress = tk.DoubleVar(value=0.0)

    items: list[Item] = []
    running = {"flag": False, "scanning": False, "closing": False}
    stop_event = threading.Event()
    ui_q: "queue.Queue[tuple]" = queue.Queue()
    preview_cache: dict = {}
    row_ids: dict[int, str] = {}

    # ---------- 样式 ----------
    style = ttk.Style()
    try:
        style.theme_use("vista" if sys.platform.startswith("win") else "clam")
    except Exception:
        try:
            style.theme_use("clam")
        except Exception:
            pass
    base_font = ("Microsoft YaHei UI", 10) if sys.platform.startswith("win") else ("PingFang SC", 12)
    try:
        root.option_add("*Font", base_font)
    except Exception:
        pass


    # ---------- 布局辅助 ----------
    def make_btn(parent, text, cmd, width=None):
        b = ttk.Button(parent, text=text, command=cmd)
        if width:
            b.configure(width=width)
        b.pack(side="left", padx=(0, 6))
        return b

    def section(parent, title):
        """带标题的分组框。"""
        f = ttk.LabelFrame(parent, text=title, padding=10)
        f.pack(fill="x", pady=(0, 10))
        return f

    # ---------- 行为 / 预览 / 转换处理 ----------
    # ---------- 行为 ----------
    def update_q_label():
        lbl_q.configure(text=str(var_quality.get()))

    def update_outdir_state():
        st = "normal" if var_outmode.get() == "custom" and not is_busy() else "disabled"
        ent_out.configure(state=st)
        btn_out.configure(state=st)

    def is_busy():
        return running["flag"] or running["scanning"]

    def update_format_state():
        supports_lossless = OUT_FORMATS[var_fmt.get()][0] in ("webp", "png")
        if not supports_lossless:
            var_lossless.set(False)
        chk_lossless.state(["!disabled"] if supports_lossless and not is_busy() else ["disabled"])
        scale.state(["disabled"] if is_busy() or var_lossless.get() else ["!disabled"])

    def update_controls():
        busy = is_busy()
        for control in (btn_add_files, btn_add_dir, btn_remove, btn_clear, btn_run):
            control.state(["disabled"] if busy else ["!disabled"])
        btn_retry.state(["!disabled"] if not busy and any(it.status == "失败" for it in items)
                        else ["disabled"])
        btn_stop.state(["!disabled"] if busy and not stop_event.is_set() else ["disabled"])

        def set_children(parent):
            for child in parent.winfo_children():
                if isinstance(child, (ttk.Entry, ttk.Combobox, ttk.Checkbutton,
                                      ttk.Radiobutton, ttk.Scale, ttk.Button)):
                    child.state(["disabled"] if busy else ["!disabled"])
                set_children(child)
        for group in (f1, f2, f3):
            set_children(group)
        update_outdir_state()
        update_format_state()

    def refresh_list(select_last=False):
        selected = {tree.item(i, "values")[0] for i in tree.selection()}
        children = tree.get_children()
        if children:
            tree.delete(*children)
        row_ids.clear()
        for i, it in enumerate(items):
            tag = ""
            if it.status == "完成":
                tag = "ok"
            elif it.status == "失败":
                tag = "fail"
            elif it.status in ("跳过", "已取消"):
                tag = "skip"
            tree.insert("", "end", iid=str(i),
                        values=(str(it.src), human_size(it.src_size),
                                (it.message if it.message else it.status)),
                        tags=(tag,) if tag else ())
            row_ids[id(it)] = str(i)
            if str(it.src) in selected:
                tree.selection_add(str(i))
        if select_last and items:
            tree.see(str(len(items) - 1))
        update_stat()
        schedule_preview()

    def totals():
        total_src = sum(i.src_size for i in items)
        done_src = sum(i.src_size for i in items if i.status in ("完成", "跳过") and i.src_size)
        done_dst = sum((i.dst_size or 0) for i in items if i.status in ("完成", "跳过"))
        return len(items), total_src, done_src, done_dst

    def update_stat():
        n, ts, ds, dd = totals()
        done = sum(1 for i in items if i.status == "完成")
        skipped = sum(1 for i in items if i.status == "跳过")
        cancelled = sum(1 for i in items if i.status == "已取消")
        fail = sum(1 for i in items if i.status == "失败")
        txt = f"共 {n} 张 · 已完成 {done}"
        if skipped:
            txt += f" · 跳过 {skipped}"
        if cancelled:
            txt += f" · 取消 {cancelled}"
        if fail:
            txt += f" · 失败 {fail}"
        if ds:
            save = (1 - dd / ds) * 100.0 if ds else 0
            txt += f" · {human_size(ds)} → {human_size(dd)} (省 {save:.0f}%)"
        elif ts:
            txt += f" · 合计 {human_size(ts)}"
        lbl_stat.configure(text=txt)

    def add_files():
        if is_busy():
            return
        paths = filedialog.askopenfilenames(
            title="选择图片",
            filetypes=[("图片文件", " ".join(f"*{e}" for e in sorted(READ_EXTS))),
                       ("所有文件", "*.*")])
        if paths:
            add_paths([Path(p) for p in paths])

    def add_dir():
        if is_busy():
            return
        d = filedialog.askdirectory(title="选择文件夹")
        if d:
            add_paths([Path(d)])

    def add_paths(paths: list[Path]):
        if is_busy():
            return
        running["scanning"] = True
        stop_event.clear()
        update_controls()
        var_status.set("正在扫描文件…")
        recursive = var_recursive.get()
        excluded = [Path(var_outdir.get().strip())] if var_outmode.get() == "custom" and var_outdir.get().strip() else []

        def scan():
            try:
                found = collect_files(paths, recursive=recursive, should_stop=stop_event.is_set,
                                      exclude_dirs=excluded)
                ui_q.put(("scanned", found))
            except Exception:
                ui_q.put(("error", traceback.format_exc()))
        threading.Thread(target=scan, daemon=True).start()
        pump()

    def remove_selected():
        if is_busy():
            return
        sel = sorted((int(i) for i in tree.selection()), reverse=True)
        for i in sel:
            if 0 <= i < len(items):
                items.pop(i)
        refresh_list()
        var_status.set(f"已移除 {len(sel)} 项")

    def clear_all():
        if is_busy():
            return
        if items and not messagebox.askyesno(APP_NAME, "确定清空列表吗？"):
            return
        items.clear()
        refresh_list()
        var_status.set("列表已清空")

    def pick_outdir():
        d = filedialog.askdirectory(title="选择输出文件夹")
        if d:
            var_outdir.set(d)
            var_outmode.set("custom")
            update_outdir_state()

    def copy_repo_url():
        try:
            root.clipboard_clear()
            root.clipboard_append(REPO_URL)
            var_status.set(f"已复制仓库地址: {REPO_URL}")
        except Exception:
            pass

    def show_about():
        """关于窗口: 展示项目信息并提供开源仓库入口。"""
        dlg = tk.Toplevel(root)
        dlg.title(f"关于 {APP_NAME}")
        dlg.transient(root)
        dlg.resizable(False, False)

        pad = ttk.Frame(dlg, padding=18)
        pad.pack(fill="both", expand=True)

        ttk.Label(pad, text=APP_NAME,
                  font=("Microsoft YaHei UI", 18, "bold")
                  if sys.platform.startswith("win") else ("PingFang SC", 20, "bold")).pack(anchor="w")
        ttk.Label(pad, text=f"批量图片转 WebP 工具 · v{APP_VERSION} · MIT License",
                  foreground="#555555").pack(anchor="w", pady=(2, 12))
        ttk.Label(pad, justify="left",
                  text=("双击即用，无需安装 Python。\n"
                        "支持 Windows 与 macOS，完全离线运行。\n\n"
                        "如果这个工具对你有帮助，欢迎到 GitHub 点个 ⭐ Star。")
                  ).pack(anchor="w")

        ttk.Separator(pad, orient="horizontal").pack(fill="x", pady=12)

        ttk.Label(pad, text="项目主页", foreground="#555555").pack(anchor="w")
        url_lbl = tk.Label(pad, text=REPO_URL, fg="#0b6fc2", cursor="hand2",
                           font=("Consolas", 10, "underline")
                           if sys.platform.startswith("win") else ("Menlo", 11, "underline"))
        url_lbl.pack(anchor="w", pady=(2, 12))
        url_lbl.bind("<Button-1>", lambda e: open_in_browser(REPO_URL))

        btns = ttk.Frame(pad)
        btns.pack(fill="x")
        ttk.Button(btns, text="⭐ 在浏览器中打开", width=16,
                   command=lambda: open_in_browser(REPO_URL)).pack(side="left")
        ttk.Button(btns, text="复制地址", width=10,
                   command=copy_repo_url).pack(side="left", padx=(6, 0))
        ttk.Button(btns, text="关闭", width=8,
                   command=dlg.destroy).pack(side="right")

        # 居中到主窗口
        dlg.update_idletasks()
        try:
            x = root.winfo_rootx() + (root.winfo_width() - dlg.winfo_width()) // 2
            y = root.winfo_rooty() + (root.winfo_height() - dlg.winfo_height()) // 3
            dlg.geometry(f"+{max(0, x)}+{max(0, y)}")
        except Exception:
            pass
        dlg.bind("<Escape>", lambda e: dlg.destroy())
        try:
            dlg.grab_set()
        except Exception:
            pass
        return dlg

    def show_about_safe():
        try:
            show_about()
        except Exception:
            messagebox.showinfo(f"关于 {APP_NAME}",
                                f"{APP_NAME} v{APP_VERSION}\n\n{REPO_URL}")

    # ---- 预览 ----
    prev_job = {"id": None}

    def schedule_preview():
        if prev_job["id"]:
            try:
                root.after_cancel(prev_job["id"])
            except Exception:
                pass
        prev_job["id"] = root.after(120, do_preview)

    def clear_preview():
        canvas.delete("all")
        cached = preview_cache.pop("thumbnail", None)
        if cached is not None:
            cached.close()
        preview_cache.clear()

    def do_preview():
        prev_job["id"] = None
        if running["closing"] or Image is None or ImageTk is None:
            return
        sel = tree.selection()
        canvas.delete("all")
        if not sel:
            clear_preview()
            lbl_prev_info.configure(text="选中左侧图片即可预览")
            return
        try:
            it = items[int(sel[0])]
            stat = it.src.stat()
            key = (_key(it.src), stat.st_mtime_ns, stat.st_size)
            if preview_cache.get("key") != key:
                clear_preview()
                thumbnail, size = load_preview(it.src)
                preview_cache.update(key=key, thumbnail=thumbnail, size=size)
            cw = max(canvas.winfo_width() - 20, 1)
            ch = max(canvas.winfo_height() - 20, 1)
            with preview_cache["thumbnail"].copy() as thumb:
                thumb.thumbnail((cw, ch), Image.LANCZOS)
                canvas_img = ImageTk.PhotoImage(thumb, master=root)
            preview_cache["img"] = canvas_img
            canvas.create_image(canvas.winfo_width() // 2, canvas.winfo_height() // 2,
                                image=canvas_img, anchor="center")
            w0, h0 = preview_cache["size"]
            actual = f"\n输出 {human_size(it.dst_size)} · {Path(it.dst).name}" if it.status == "完成" and it.dst else ""
            lbl_prev_info.configure(
                text=f"{it.src.name}\n尺寸 {w0}×{h0}　原始大小 {human_size(stat.st_size)}{actual}")
        except Exception as exc:
            clear_preview()
            lbl_prev_info.configure(text="此文件无法预览；其他图片仍可继续转换")
            canvas.create_text(10, 10, anchor="nw", fill="#ffb4b4",
                               width=max(canvas.winfo_width() - 20, 100),
                               text=f"无法预览:\n{exc}")

    def open_output_folder():
        selected = tree.selection()
        if selected:
            item = items[int(selected[0])]
            folder = Path(item.dst).parent if item.dst else item.src.parent
        elif var_outmode.get() == "custom" and var_outdir.get().strip():
            folder = Path(var_outdir.get().strip())
        elif items:
            folder = items[0].src.parent
        else:
            messagebox.showinfo(APP_NAME, "请先添加图片或选择输出文件夹。")
            return
        try:
            folder = folder.resolve()
            if not folder.is_dir():
                raise ValueError("输出文件夹尚不存在，请先完成转换。")
            if sys.platform.startswith("win"):
                os.startfile(str(folder))
            else:
                import subprocess
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(folder)])
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"无法打开文件夹：{exc}")

    # ---- 转换 ----
    def build_options() -> Options:
        fmt, ext = OUT_FORMATS.get(var_fmt.get(), ("webp", ".webp"))
        try:
            me = int(str(var_maxedge.get()).strip() or "0")
        except ValueError as exc:
            raise ValueError("最长边必须为非负整数，0 表示不缩放") from exc
        opts = Options(
            quality=int(var_quality.get()),
            lossless=bool(var_lossless.get()),
            out_fmt=fmt,
            out_ext=ext,
            keep_structure=bool(var_keep.get()),
            overwrite=bool(var_overwrite.get()),
            flatten=bool(var_flatten.get()),
            bg=var_bg.get() or "#ffffff",
            max_edge=me,
            also_smaller_only=bool(var_smaller_only.get()),
            recursive=bool(var_recursive.get()),
        )
        validate_options(opts)
        return opts

    def resolve_out_root() -> Path | None:
        """返回输出根目录; None 表示"就在原图旁边"。"""
        if var_outmode.get() == "custom":
            value = var_outdir.get().strip()
            if not value:
                raise ValueError("请先选择输出文件夹")
            d = Path(value).resolve()
            d.mkdir(parents=True, exist_ok=True)
            return d
        return None

    def start(retry_failed=False):
        if is_busy():
            return
        if not items:
            messagebox.showinfo(APP_NAME, "请先添加要转换的图片或文件夹。")
            return
        try:
            opts = build_options()
            out_root = resolve_out_root()
        except Exception as exc:
            messagebox.showerror(APP_NAME, str(exc))
            return

        todo = [i for i in items if i.status == "失败"] if retry_failed else [
            i for i in items if i.status not in ("完成", "跳过")]
        if not todo:
            if retry_failed:
                return
            if not messagebox.askyesno(APP_NAME, "所有图片都已处理完成，要按当前设置重新转换一遍吗？"):
                return
            todo = list(items)
        for item in todo:
            item.status, item.message, item.dst, item.dst_size = "等待", "", "", 0
        refresh_list()

        running["flag"] = True
        stop_event.clear()
        update_controls()
        var_progress.set(0.0)
        var_status.set(f"正在转换 0/{len(todo)} …")

        def worker():
            try:
                def prog(done, total, item):
                    # 取消项在最终刷新时统一显示，避免大量取消消息堵塞界面。
                    if item.status != "已取消":
                        ui_q.put(("row", item, done, total))
                res = run_batch(todo, opts, out_root, progress=prog,
                                should_stop=stop_event.is_set)
                ui_q.put(("done", res, len(todo)))
            except Exception:
                ui_q.put(("error", traceback.format_exc()))
        threading.Thread(target=worker, daemon=True).start()
        pump()

    def finish_close():
        if prev_job["id"]:
            root.after_cancel(prev_job["id"])
            prev_job["id"] = None
        clear_preview()
        root.destroy()

    def pump():
        changed = False
        try:
            # 每次最多更新一小批，给重绘、停止按钮和窗口事件留出处理时间。
            for _ in range(150):
                msg = ui_q.get_nowait()
                kind = msg[0]
                if kind == "row":
                    item, done, total = msg[1:]
                    row_id = row_ids.get(id(item))
                    if row_id is not None and tree.exists(row_id):
                        tag = {"完成": "ok", "失败": "fail", "跳过": "skip"}.get(item.status, "")
                        tree.item(row_id, values=(str(item.src), human_size(item.src_size),
                                                  item.message or item.status),
                                  tags=(tag,) if tag else ())
                    changed = True
                    var_progress.set(done / max(1, total) * 100.0)
                    if not stop_event.is_set():
                        var_status.set(f"正在转换 {done}/{total} …")
                elif kind == "scanned":
                    running["scanning"] = False
                    if running["closing"]:
                        finish_close()
                        return
                    found = msg[1]
                    have = {_key(item.src) for item in items}
                    new = [item for item in found if _key(item.src) not in have]
                    items.extend(new)
                    refresh_list(select_last=True)
                    prefix = "扫描已停止，" if stop_event.is_set() else ""
                    var_status.set(f"{prefix}已添加 {len(new)} 张图片，忽略重复 {len(found) - len(new)} 张")
                    update_controls()
                    return
                elif kind == "done":
                    res, total = msg[1:]
                    running["flag"] = False
                    if running["closing"]:
                        finish_close()
                        return
                    processed = res.ok + res.skipped + res.failed
                    var_progress.set(processed / max(1, total) * 100.0)
                    verb = "已停止" if res.cancelled else "完成"
                    summary = (f"{verb} · 成功 {res.ok} · 跳过 {res.skipped} · 失败 {res.failed}"
                               f" · 取消 {res.cancelled} · 耗时 {res.elapsed:.1f}s")
                    var_status.set(summary)
                    refresh_list()
                    update_controls()
                    if res.errors:
                        detail = "\n".join(f"· {Path(p).name}: {m}" for p, m in res.errors[:12])
                        if len(res.errors) > 12:
                            detail += f"\n… 另有 {len(res.errors) - 12} 个失败"
                        messagebox.showwarning(APP_NAME, f"有 {res.failed} 张图片转换失败，可点击「重试失败」:\n\n{detail}")
                    return
                elif kind == "error":
                    running["flag"] = running["scanning"] = False
                    if running["closing"]:
                        finish_close()
                        return
                    update_controls()
                    var_status.set("发生错误，可以调整设置后重试")
                    messagebox.showerror(APP_NAME, msg[1][-2000:])
                    return
        except queue.Empty:
            pass
        if changed:
            update_stat()
        if is_busy():
            root.after(80, pump)

    def stop():
        if not is_busy():
            return
        stop_event.set()
        btn_stop.state(["disabled"])
        var_status.set("正在停止，等待当前图片处理结束…")

    def on_close():
        if is_busy():
            running["closing"] = True
            stop()
            var_status.set("正在停止并清理临时文件，完成后自动关闭…")
        else:
            finish_close()


    # ---------- 界面布局 ----------
    # ---------- 布局 ----------
    outer = ttk.Frame(root, padding=10)
    outer.pack(fill="both", expand=True)

    # 顶部工具条
    bar = ttk.Frame(outer)
    bar.pack(fill="x", pady=(0, 8))

    btn_add_files = make_btn(bar, "➕ 添加图片", lambda: add_files())
    btn_add_dir = make_btn(bar, "📁 添加文件夹", lambda: add_dir())
    btn_remove = make_btn(bar, "➖ 移除选中", lambda: remove_selected())
    btn_clear = make_btn(bar, "🗑 清空列表", lambda: clear_all())

    btn_run = ttk.Button(bar, text="▶  开始转换", command=lambda: start())
    btn_run.pack(side="right", padx=(6, 0))
    btn_stop = ttk.Button(bar, text="■ 停止", command=lambda: stop(), state="disabled")
    btn_stop.pack(side="right")
    btn_retry = ttk.Button(bar, text="重试失败", command=lambda: start(retry_failed=True), state="disabled")
    btn_retry.pack(side="right", padx=(0, 6))
    # 开源仓库入口
    btn_about = ttk.Button(bar, text="⭐ 关于 / 项目主页", command=lambda: show_about_safe())
    btn_about.pack(side="right", padx=(0, 6))

    # 主体: 左列表 + 右设置
    body = ttk.Panedwindow(outer, orient="horizontal")
    body.pack(fill="both", expand=True)

    left = ttk.Frame(body)
    right = ttk.Frame(body, padding=(12, 0, 0, 0))
    body.add(left, weight=3)
    body.add(right, weight=2)

    # --- 左: 文件列表 ---
    cols = ("name", "size", "status")
    tree = ttk.Treeview(left, columns=cols, show="headings", selectmode="extended")
    tree.heading("name", text="文件")
    tree.heading("size", text="原始大小")
    tree.heading("status", text="状态 / 结果")
    tree.column("name", width=330, anchor="w")
    tree.column("size", width=90, anchor="e", stretch=False)
    tree.column("status", width=260, anchor="w")
    vsb = ttk.Scrollbar(left, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")
    tree.tag_configure("ok", foreground="#137333")
    tree.tag_configure("fail", foreground="#c5221f")
    tree.tag_configure("skip", foreground="#8a6d00")

    tree.bind("<<TreeviewSelect>>", lambda e: schedule_preview())

    # --- 右: 预览 + 设置 ---
    nb = ttk.Notebook(right)
    nb.pack(fill="both", expand=True)

    tab_prev = ttk.Frame(nb, padding=10)
    tab_set = ttk.Frame(nb, padding=10)
    nb.add(tab_prev, text="预览")
    nb.add(tab_set, text="设置")

    # 预览页
    prev_wrap = ttk.Frame(tab_prev)
    prev_wrap.pack(fill="both", expand=True)
    canvas = tk.Canvas(prev_wrap, background="#2b2b2b", highlightthickness=0)
    canvas.pack(fill="both", expand=True)
    lbl_prev_info = ttk.Label(tab_prev, text="选中左侧图片即可预览", justify="left", anchor="w")
    lbl_prev_info.pack(fill="x", pady=(8, 0))
    ttk.Button(tab_prev, text="打开输出文件夹", command=open_output_folder).pack(anchor="w", pady=(6, 0))
    canvas.bind("<Configure>", lambda e: schedule_preview())

    # 设置页
    f1 = section(tab_set, "输出格式与质量")
    row = ttk.Frame(f1); row.pack(fill="x")
    ttk.Label(row, text="格式", width=10).pack(side="left")
    cmb_fmt = ttk.Combobox(row, textvariable=var_fmt, values=list(OUT_FORMATS.keys()),
                           state="readonly", width=18)
    cmb_fmt.pack(side="left")
    cmb_fmt.bind("<<ComboboxSelected>>", lambda e: update_format_state())
    row2 = ttk.Frame(f1); row2.pack(fill="x", pady=(8, 0))
    ttk.Label(row2, text="质量", width=10).pack(side="left")
    scale = ttk.Scale(row2, from_=1, to=100, variable=var_quality,
                      command=lambda v: (var_quality.set(int(float(v))), update_q_label()))
    scale.pack(side="left", fill="x", expand=True)
    lbl_q = ttk.Label(row2, text="80", width=4)
    lbl_q.pack(side="left", padx=(6, 0))
    chk_lossless = ttk.Checkbutton(f1, text="无损模式（仅 WebP / PNG）",
                                    variable=var_lossless, command=update_format_state)
    chk_lossless.pack(anchor="w", pady=(8, 0))
    ttk.Checkbutton(f1, text="智能模式：仅保存体积更小的结果",
                    variable=var_smaller_only).pack(anchor="w")

    f2 = section(tab_set, "输出位置")
    ttk.Radiobutton(f2, text="与原图放在一起", variable=var_outmode,
                    value="same", command=update_outdir_state).pack(anchor="w")
    r = ttk.Frame(f2); r.pack(fill="x")
    ttk.Radiobutton(r, text="指定文件夹:", variable=var_outmode,
                    value="custom", command=update_outdir_state).pack(side="left")
    ent_out = ttk.Entry(r, textvariable=var_outdir)
    ent_out.pack(side="left", fill="x", expand=True, padx=(6, 6))
    btn_out = ttk.Button(r, text="浏览…", command=lambda: pick_outdir(), width=8)
    btn_out.pack(side="left")
    ttk.Checkbutton(f2, text="保留子文件夹结构", variable=var_keep).pack(anchor="w", pady=(8, 0))
    ttk.Checkbutton(f2, text="覆盖已有输出（始终保护本批原图）",
                    variable=var_overwrite).pack(anchor="w")

    f3 = section(tab_set, "图像处理")
    ttk.Checkbutton(f3, text="递归处理子文件夹", variable=var_recursive).pack(anchor="w")
    ttk.Checkbutton(f3, text="透明区域填充为背景色(而非保留透明)",
                    variable=var_flatten).pack(anchor="w")
    r3 = ttk.Frame(f3); r3.pack(fill="x", pady=(6, 0))
    ttk.Label(r3, text="背景色", width=10).pack(side="left")
    ttk.Entry(r3, textvariable=var_bg, width=10).pack(side="left")
    ttk.Label(r3, text="  最长边(像素, 0=不缩放)", width=24).pack(side="left")
    ttk.Entry(r3, textvariable=var_maxedge, width=8).pack(side="left")

    # 关于 / 开源仓库
    f4 = section(tab_set, "关于")
    ttk.Label(f4, text=f"{APP_NAME} v{APP_VERSION} · MIT License",
              foreground="#555555").pack(anchor="w")
    link = tk.Label(f4, text=REPO_URL, fg="#0b6fc2", cursor="hand2",
                    font=("Consolas", 9, "underline") if sys.platform.startswith("win")
                    else ("Menlo", 10, "underline"))
    link.pack(anchor="w", pady=(2, 6))
    link.bind("<Button-1>", lambda e: open_in_browser(REPO_URL))
    link.bind("<Enter>", lambda e: link.configure(fg="#0a86ea"))
    link.bind("<Leave>", lambda e: link.configure(fg="#0b6fc2"))
    about_btns = ttk.Frame(f4)
    about_btns.pack(anchor="w")
    ttk.Button(about_btns, text="⭐ 打开项目主页",
               command=lambda: open_in_browser(REPO_URL)).pack(side="left")
    ttk.Button(about_btns, text="报告问题 / 建议",
               command=lambda: open_in_browser(
                   f"{REPO_URL}/issues/new/choose")).pack(side="left", padx=(6, 0))

    # 底部: 进度 + 状态 + 统计 + 仓库链接
    bottom = ttk.Frame(outer)
    bottom.pack(fill="x", pady=(10, 0))
    pb = ttk.Progressbar(bottom, variable=var_progress, maximum=100.0)
    pb.pack(fill="x")
    line = ttk.Frame(bottom)
    line.pack(fill="x", pady=(6, 0))
    ttk.Label(line, textvariable=var_status, anchor="w").pack(side="left", fill="x", expand=True)
    lbl_stat = ttk.Label(line, text="", anchor="e")
    lbl_stat.pack(side="right")
    # 状态栏右下角的仓库入口, 点一下就打开浏览器
    repo_link = tk.Label(line, text="GitHub ⭐", fg="#0b6fc2", cursor="hand2",
                         font=("Microsoft YaHei UI", 9, "underline")
                         if sys.platform.startswith("win") else ("PingFang SC", 10, "underline"))
    repo_link.pack(side="right", padx=(10, 0))
    repo_link.bind("<Button-1>", lambda e: open_in_browser(REPO_URL))
    repo_link.bind("<Enter>", lambda e: repo_link.configure(fg="#0a86ea"))
    repo_link.bind("<Leave>", lambda e: repo_link.configure(fg="#0b6fc2"))


    # 控件已就绪, 现在才能安全地初始化它们的状态
    update_controls()
    update_q_label()
    refresh_list()

    # 快捷键
    root.bind("<Control-o>", lambda e: add_files())
    root.bind("<Control-O>", lambda e: add_files())
    tree.bind("<Delete>", lambda e: remove_selected())
    tree.bind("<Control-a>", lambda e: tree.selection_set(tree.get_children()))
    root.bind("<Escape>", lambda e: stop())
    root.bind("<F5>", lambda e: start())
    root.bind("<Control-u>", lambda e: show_about_safe())
    root.bind("<Control-U>", lambda e: show_about_safe())

    # 拖拽
    dropped = enable_windows_drop(root, lambda files: add_paths([Path(f) for f in files]))
    if not dropped:
        var_status.set("提示: 也可直接点「添加图片」/「添加文件夹」选择文件")

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()
    return 0


# ----------------------------------------------------------------------------
# 命令行
# ----------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="webpforge",
        description="批量把图片转换为 WebP(或其他格式)。不带参数运行会打开图形界面。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例:\n"
               "  webpforge --cli -i ./照片 -o ./输出 -q 80 --keep\n"
               "  webpforge --cli -i a.png b.jpg -o out --lossless\n")
    p.add_argument("--cli", action="store_true", help="使用命令行模式(不打开界面)")
    p.add_argument("-i", "--input", nargs="+", required=False,
                   help="输入图片、文件夹或通配符(可多个)")
    p.add_argument("-o", "--outdir", default=None, help="输出文件夹(默认与源文件同目录)")
    p.add_argument("-q", "--quality", type=int, default=80, help="质量 1-100 (默认 80)")
    p.add_argument("-f", "--format", default="webp",
                   choices=["webp", "png", "jpeg", "jpg", "avif"], help="输出格式(默认 webp)")
    p.add_argument("--lossless", action="store_true", help="无损编码，仅支持 WebP / PNG")
    p.add_argument("--keep", action="store_true", help="保留子文件夹结构")
    p.add_argument("--overwrite", action="store_true", help="覆盖已有输出，始终保护本批输入文件")
    p.add_argument("--flatten", action="store_true", help="透明区域填充背景色")
    p.add_argument("--bg", default="#ffffff", help="填充背景色(默认 #ffffff)")
    p.add_argument("--max-edge", type=int, default=0, help="限制最长边像素(0=不缩放)")
    p.add_argument("--smaller-only", action="store_true", help="仅当结果更小才写入")
    p.add_argument("--no-recursive", action="store_true", help="不递归子文件夹")
    p.add_argument("-j", "--workers", type=int, default=0, help="并发线程数(默认自动)")
    p.add_argument("--json", action="store_true", help="输出 JSON 结果")
    p.add_argument("--selftest", nargs="?", const="", metavar="REPORT",
                   help="环境与转换自检，可指定报告文件路径")
    p.add_argument("-v", "--version", action="version", version=f"{APP_NAME} {APP_VERSION}")
    return p


def run_cli(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.selftest is not None:
        return run_selftest(Path(args.selftest) if args.selftest else None)

    if not args.input:
        parser.print_help()
        return 2

    fmt = "jpeg" if args.format == "jpg" else args.format
    ext = {"webp": ".webp", "png": ".png", "jpeg": ".jpg", "avif": ".avif"}[fmt]
    opts = Options(
        quality=args.quality,
        lossless=args.lossless,
        out_fmt=fmt,
        out_ext=ext,
        keep_structure=args.keep,
        overwrite=args.overwrite,
        flatten=args.flatten,
        bg=args.bg,
        max_edge=args.max_edge,
        also_smaller_only=args.smaller_only,
        workers=args.workers,
        recursive=not args.no_recursive,
    )

    try:
        validate_options(opts)
        if args.outdir is not None and not args.outdir.strip():
            raise ValueError("输出文件夹不能为空")
    except ValueError as exc:
        parser.error(str(exc))

    out_root = Path(args.outdir).resolve() if args.outdir else None
    roots = [Path(x) for x in args.input]
    items = collect_files(roots, recursive=opts.recursive,
                          exclude_dirs=[out_root] if out_root is not None else [])
    if not items:
        print("没有找到可转换的图片。", file=sys.stderr)
        return 1

    quiet = args.json
    if not quiet:
        print(f"{APP_NAME} v{APP_VERSION}")
        print(f"待转换 {len(items)} 张 → {fmt.upper()}"
              + (f" / 质量 {opts.quality}" if not opts.lossless else " / 无损"))
        print(f"输出目录: {out_root.resolve() if out_root else '与源文件同目录'}")
        print("-" * 64)

    def prog(done, total, it):
        if quiet:
            return
        mark = {"完成": "✓", "跳过": "–", "失败": "✗", "已取消": "·"}.get(it.status, "?")
        print(f"[{done:>4}/{total}] {mark} {it.src.name:<40.40} {it.message}")

    def do(res: Result) -> int:
        if args.json:
            print(json.dumps({
                "total": len(items), "ok": res.ok, "skipped": res.skipped,
                "failed": res.failed, "cancelled": res.cancelled, "src_bytes": res.src_bytes,
                "dst_bytes": res.dst_bytes, "elapsed": round(res.elapsed, 2),
                "errors": [{"file": p, "error": m} for p, m in res.errors],
                "items": [{"source": str(it.src), "output": it.dst or None,
                           "status": {"完成": "ok", "跳过": "skipped", "失败": "failed",
                                      "已取消": "cancelled"}[it.status],
                           "src_bytes": it.src_size, "dst_bytes": it.dst_size,
                           "message": it.message} for it in items],
            }, ensure_ascii=False, indent=2))
        else:
            print("-" * 64)
            line = (f"完成: 成功 {res.ok} · 跳过 {res.skipped} · 失败 {res.failed} · 取消 {res.cancelled} · "
                    f"耗时 {res.elapsed:.1f}s")
            if res.src_bytes:
                save = (1 - res.dst_bytes / res.src_bytes) * 100.0
                line += f"\n体积: {human_size(res.src_bytes)} → {human_size(res.dst_bytes)} (省 {save:.1f}%)"
            print(line)
            for p, m in res.errors[:20]:
                print(f"  ! {p}: {m}", file=sys.stderr)
        return 130 if res.cancelled else (0 if res.failed == 0 else 3)

    import signal
    stop_event = threading.Event()
    handle_signal = threading.current_thread() is threading.main_thread()
    if handle_signal:
        previous_handler = signal.signal(signal.SIGINT, lambda *_: stop_event.set())
    try:
        res = run_batch(items, opts, out_root, progress=prog, should_stop=stop_event.is_set)
    finally:
        if handle_signal:
            signal.signal(signal.SIGINT, previous_handler)
    return do(res)


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def run_selftest(report_path: Path | None = None) -> int:
    """自检: 在临时目录里跑一遍完整流程, 结果写入文件。

    打包成窗口程序后没有控制台, 这是验证 exe 是否健康的最可靠方式。
    用法: WebPForge.exe --selftest [结果文件路径]
    """
    import tempfile
    lines: list[str] = []

    def log(msg: str = "") -> None:
        lines.append(msg)

    ok = True
    log(f"{APP_NAME} v{APP_VERSION} 自检")
    log(f"Python  : {sys.version.split()[0]}")
    log(f"平台    : {sys.platform}")
    log(f"冻结打包: {getattr(sys, 'frozen', False)}")
    log("-" * 52)

    # 1) 依赖检查
    try:
        import PIL
        from PIL import Image, features
        log(f"[OK] Pillow {PIL.__version__}")
        log(f"[OK] WebP 编码支持: {features.check('webp')}")
        if not features.check("webp"):
            ok = False
            log("[!!] 缺少 WebP 支持, 无法转换")
    except Exception as exc:
        ok = False
        log(f"[!!] Pillow 导入失败: {exc}")
        Image = None  # type: ignore

    # 2) tkinter 检查(界面可用性)
    try:
        import tkinter
        log(f"[OK] tkinter {tkinter.TkVersion} (图形界面可用)")
    except Exception as exc:
        ok = False
        log(f"[!!] tkinter 不可用, 无法显示界面: {exc}")

    # 3) 真实转换检查
    if Image is not None:
        try:
            with tempfile.TemporaryDirectory(prefix="wc_selftest_") as td:
                td_path = Path(td)
                # 造一张带透明的 PNG
                src = td_path / "测试图片.png"
                im = Image.new("RGBA", (120, 90), (0, 0, 0, 0))
                for x in range(60):
                    for y in range(45):
                        im.putpixel((x, y), (200, 30, 30, 255))
                im.save(src)

                items = collect_files([td_path], recursive=True)
                log(f"[OK] 扫描到 {len(items)} 个文件")
                opts = Options(quality=80, out_fmt="webp", out_ext=".webp")
                res = run_batch(items, opts, None)
                log(f"[OK] 转换结果: 成功={res.ok} 失败={res.failed} 耗时={res.elapsed:.2f}s")
                if res.ok != 1 or res.failed != 0:
                    ok = False
                    log("[!!] 转换结果不符合预期")

                produced = sorted(td_path.glob("*.webp"))
                if produced:
                    with Image.open(produced[0]) as chk:
                        log(f"[OK] 产物可读: {produced[0].name} {chk.mode} {chk.size} "
                            f"{produced[0].stat().st_size} 字节")
                        if "A" not in chk.mode:
                            ok = False
                            log("[!!] 透明度丢失")
                else:
                    ok = False
                    log("[!!] 没有产生输出文件")

                # 中文路径检查
                cn_dir = td_path / "中文目录-测试"
                cn_dir.mkdir()
                sd = td_path / "中文名源图.png"
                Image.new("RGB", (40, 40), (10, 120, 200)).save(sd)
                r2 = run_batch(collect_files([sd], recursive=False), opts, cn_dir)
                if r2.ok == 1:
                    log("[OK] 中文路径读写正常")
                else:
                    ok = False
                    log(f"[!!] 中文路径处理失败: {r2.errors}")
        except Exception as exc:
            ok = False
            log(f"[!!] 转换自检异常: {type(exc).__name__}: {exc}")
            log(traceback.format_exc())

    log("-" * 52)
    log("结论: " + ("全部通过 ✓" if ok else "存在失败 ✗"))

    text = "\n".join(lines)
    # 输出: 指定文件 > exe 同目录 > 用户主目录
    targets = []
    if report_path is not None:
        targets.append(report_path)
    if getattr(sys, "frozen", False):
        targets.append(Path(sys.executable).parent / f"{APP_NAME}_selftest.txt")
    else:
        targets.append(Path.cwd() / f"{APP_NAME}_selftest.txt")
    targets.append(Path.home() / f"{APP_NAME}_selftest.txt")

    for t in targets:
        try:
            t.parent.mkdir(parents=True, exist_ok=True)
            t.write_text(text, encoding="utf-8")
            break
        except Exception:
            continue

    try:
        print(text)
    except Exception:
        pass
    return 0 if ok else 1


def fatal_console_hint() -> None:
    """Windows 无控制台时把崩溃信息写成文件, 方便排查。"""
    try:
        log = Path.home() / f"{APP_NAME.lower()}_error.log"
        log.write_text(traceback.format_exc(), encoding="utf-8")
    except Exception:
        pass


def restore_cli_streams() -> None:
    """窗口版 EXE 的 CLI 保留管道重定向；交互调用时连接父控制台。"""
    if os.name != "nt":
        return
    # 重定向时标准流可能仍存在，但编码是系统 GBK，无法输出 ✓ 或任意文件名。
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    if sys.stdout is not None and sys.stderr is not None:
        return
    import ctypes
    from ctypes import wintypes
    import msvcrt

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetStdHandle.argtypes = [wintypes.DWORD]
    kernel.GetStdHandle.restype = wintypes.HANDLE
    kernel.AttachConsole.argtypes = [wintypes.DWORD]
    kernel.AttachConsole.restype = wintypes.BOOL
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.DuplicateHandle.argtypes = [wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE,
                                      ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD,
                                      wintypes.BOOL, wintypes.DWORD]
    kernel.DuplicateHandle.restype = wintypes.BOOL
    handles = {"stdout": kernel.GetStdHandle(-11), "stderr": kernel.GetStdHandle(-12)}
    invalid = (None, 0, wintypes.HANDLE(-1).value)
    if any(handle in invalid for handle in handles.values()):
        kernel.AttachConsole(-1)
    process = kernel.GetCurrentProcess()
    for name, identifier in (("stdout", -11), ("stderr", -12)):
        if getattr(sys, name) is not None:
            continue
        handle = handles[name]
        if handle in invalid:
            handle = kernel.GetStdHandle(identifier)
        duplicate = wintypes.HANDLE()
        if handle not in invalid and kernel.DuplicateHandle(process, handle, process,
                                                             ctypes.byref(duplicate), 0, False, 2):
            fd = msvcrt.open_osfhandle(duplicate.value, os.O_WRONLY | os.O_BINARY)
            setattr(sys, name, os.fdopen(fd, "w", encoding="utf-8", errors="replace", buffering=1))


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if argv:
            restore_cli_streams()
            return run_cli(argv)
        return launch_gui()
    except Exception:
        fatal_console_hint()
        if sys.stderr is not None:
            traceback.print_exc()
        if argv:
            return 1
        try:
            import tkinter.messagebox as mb
            mb.showerror(APP_NAME, "程序发生错误:\n\n" + traceback.format_exc()[-1500:])
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
