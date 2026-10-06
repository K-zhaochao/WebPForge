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

项目主页: https://github.com/<your-name>/webpforge
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
from concurrent.futures import ThreadPoolExecutor
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

_NAME_LOCK = threading.Lock()
_RESERVED: set[str] = set()


def _key(path: Path) -> str:
    try:
        return os.path.normcase(str(path.resolve()))
    except OSError:
        return os.path.normcase(os.path.abspath(str(path)))


def reserve_unique_path(path: Path) -> Path:
    """在并发环境下为 path 分配一个唯一的输出文件名。

    name.webp -> name(1).webp -> name(2).webp ... 绝不覆盖已存在的文件。
    """
    with _NAME_LOCK:
        stem, suffix, parent = path.stem, path.suffix, path.parent
        cand = path
        i = 0
        while True:
            k = _key(cand)
            if k not in _RESERVED and not cand.exists():
                _RESERVED.add(k)
                return cand
            i += 1
            if i > 100000:
                raise OSError(f"无法为 {path} 找到可用的文件名")
            cand = parent / f"{stem}({i}){suffix}"


def release_reserved_path(path: Path) -> None:
    """转换失败时释放预定, 让后续任务可以复用这个名字。"""
    with _NAME_LOCK:
        _RESERVED.discard(_key(path))


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
    also_smaller_only: bool = False  # 仅当结果更小才写盘(用于 webp 输出)
    workers: int = 0               # 线程数, 0 = 自动
    recursive: bool = True


@dataclass
class Item:
    src: Path
    rel: str = ""            # 相对于扫描根目录的路径(用于保留结构)
    status: str = "等待"      # 等待 / 转换中 / 完成 / 跳过 / 失败
    dst: str = ""
    src_size: int = 0
    dst_size: int = 0
    message: str = ""


@dataclass
class Result:
    ok: int = 0
    skipped: int = 0
    failed: int = 0
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
    try:
        tmp = Image.new("RGB", (1, 1), bg)
        return tmp.getpixel((0, 0))
    except Exception:
        return (255, 255, 255)


def resolve_target_dir(item: Item, opts: Options, out_root: Path | None) -> Path:
    """决定某张图片应该写到哪个目录。

    out_root 为 None 或 "." 时表示"就在原图旁边"(原地输出);
    指定输出目录时, keep_structure 决定是否重建子文件夹层级。
    """
    if out_root is None or str(out_root) in (".", ""):
        return item.src.parent
    if opts.keep_structure and item.rel and item.rel not in (".", ""):
        return out_root / item.rel
    return out_root


def convert_one(item: Item, opts: Options, out_root: Path | None) -> Item:
    """转换单张图片。就地修改 item 并返回。"""
    Image, ImageOps = _pil()
    src = item.src

    try:
        item.src_size = src.stat().st_size
    except OSError:
        item.src_size = 0

    # 计算输出路径(并发安全, 绝不覆盖已有文件)
    target_dir = resolve_target_dir(item, opts, out_root)
    target_dir.mkdir(parents=True, exist_ok=True)
    dst = reserve_unique_path(target_dir / (src.stem + opts.out_ext))

    def new_tmp() -> Path:
        """同目录下的唯一临时文件, 保证原子替换且线程间不打架。"""
        fd, name = tempfile.mkstemp(prefix=".wc_tmp_", suffix=opts.out_ext, dir=str(target_dir))
        os.close(fd)
        tmp_holder["path"] = name
        return Path(name)

    tmp_holder: dict = {"path": None}
    try:
        with Image.open(src) as im:
            im.load()

            # 必须在任何变换之前读取帧数: exif_transpose/resize 都会丢掉多帧信息
            n_frames = int(getattr(im, "n_frames", 1) or 1)
            fmt = opts.out_fmt

            # 动画图片(GIF/动态 WebP) → 保留全部帧
            if n_frames > 1 and fmt in ("webp", "gif"):
                total_dur = int(im.info.get("duration", 100) or 100)
                frames, durations = [], []
                for idx in range(n_frames):
                    try:
                        im.seek(idx)
                    except EOFError:
                        break
                    fr = im.convert("RGBA") if im.mode not in ("RGB", "RGBA") else im.copy()
                    if opts.flatten:
                        bg_rgb = _flatten_color(Image, opts.bg)
                        canvas = Image.new("RGB", fr.size, bg_rgb)
                        if fr.mode == "RGBA":
                            canvas.paste(fr, mask=fr.split()[-1])
                        else:
                            canvas.paste(fr)
                        fr = canvas
                    if opts.max_edge and max(fr.size) > opts.max_edge:
                        sc = opts.max_edge / float(max(fr.size))
                        fr = fr.resize((max(1, round(fr.width * sc)), max(1, round(fr.height * sc))),
                                       Image.LANCZOS)
                    frames.append(fr)
                    durations.append(max(20, int(im.info.get("duration", total_dur) or total_dur)))

                if len(frames) > 1:
                    save_kwargs: dict = {
                        "save_all": True,
                        "append_images": frames[1:],
                        "duration": durations,
                        "loop": int(im.info.get("loop", 0) or 0),
                        "lossless": bool(opts.lossless),
                    }
                    if not opts.lossless:
                        save_kwargs["quality"] = int(opts.quality)
                        save_kwargs["method"] = 6
                    tmp_dst = new_tmp()
                    try:
                        frames[0].save(tmp_dst, format="WEBP", **save_kwargs)
                    except TypeError:
                        frames[0].save(tmp_dst, format="WEBP", save_all=True,
                                       append_images=frames[1:], quality=int(opts.quality))

                    new_size = tmp_dst.stat().st_size
                    if opts.also_smaller_only and item.src_size and new_size >= item.src_size:
                        tmp_dst.unlink(missing_ok=True)
                        release_reserved_path(dst)
                        item.status, item.dst_size = "跳过", item.src_size
                        item.message = f"原文件更小({human_size(item.src_size)}), 已保留原图"
                        return item
                    os.replace(tmp_dst, dst)
                    item.dst = str(dst)
                    item.dst_size = new_size
                    item.status = "完成"
                    item.message = (f"{human_size(item.src_size)} → {human_size(new_size)}"
                                    f" · 动画 {len(frames)} 帧")
                    return item

            # 手机照片的 EXIF 旋转(单帧图片才做)
            try:
                im = ImageOps.exif_transpose(im)
            except Exception:
                pass

            # 限制尺寸
            if opts.max_edge and max(im.size) > opts.max_edge:
                scale = opts.max_edge / float(max(im.size))
                new_size = (max(1, round(im.width * scale)), max(1, round(im.height * scale)))
                im = im.resize(new_size, Image.LANCZOS)

            # 透明背景处理
            if opts.flatten and im.mode in ("RGBA", "LA", "PA", "P"):
                if im.mode == "P":
                    im = im.convert("RGBA")
                if im.mode in ("RGBA", "LA", "PA"):
                    bg_rgb = _flatten_color(Image, opts.bg)
                    rgba = im.convert("RGBA")
                    canvas = Image.new("RGB", rgba.size, bg_rgb)
                    canvas.paste(rgba, mask=rgba.split()[-1])
                    im = canvas

            save_kwargs: dict = {}

            if fmt == "webp":
                save_kwargs["lossless"] = bool(opts.lossless)
                if not opts.lossless:
                    save_kwargs["quality"] = int(opts.quality)
                    save_kwargs["method"] = 6
                # 保留 EXIF (若存在)
                exif = None
                try:
                    exif = im.info.get("exif")
                except Exception:
                    exif = None
                if exif:
                    save_kwargs["exif"] = exif
            elif fmt == "jpeg":
                if im.mode not in ("RGB", "L"):
                    if im.mode in ("RGBA", "LA", "PA"):
                        bg_rgb = _flatten_color(Image, opts.bg)
                        rgba = im.convert("RGBA")
                        canvas = Image.new("RGB", rgba.size, bg_rgb)
                        canvas.paste(rgba, mask=rgba.split()[-1])
                        im = canvas
                    else:
                        im = im.convert("RGB")
                save_kwargs["quality"] = int(opts.quality)
                save_kwargs["optimize"] = True
                save_kwargs["progressive"] = True
                save_kwargs["subsampling"] = 0 if opts.quality >= 90 else 2
            elif fmt == "png":
                if im.mode == "P":
                    im = im.convert("RGBA" if "transparency" in im.info else "RGB")
                save_kwargs["optimize"] = True
                # 质量 < 100 时走调色板, 体积可小很多
                if opts.quality < 100 and im.mode in ("RGB", "RGBA", "L", "LA"):
                    colors = 256 if opts.quality >= 75 else max(8, int(256 * opts.quality / 100))
                    try:
                        if im.mode == "RGBA":
                            # 保留 1 位透明: 需要 ALPHA 转 TRANSPARENCY 的量化结果
                            im = im.quantize(colors=colors, method=Image.MEDIANCUT)
                        elif im.mode == "LA":
                            im = im.convert("RGBA").quantize(colors=colors, method=Image.MEDIANCUT)
                        else:
                            im = im.quantize(colors=colors, method=Image.MEDIANCUT)
                    except Exception:
                        pass
            elif fmt == "avif":
                save_kwargs["quality"] = int(opts.quality)
                if opts.lossless:
                    save_kwargs["lossless"] = True

            # 避免 EXIF 重复旋转: 已 apply 过 transpose, 清掉方向标记
            try:
                ex = im.getexif()
                if ex and 0x0112 in ex:
                    ex[0x0112] = 1
                    if fmt != "webp":
                        save_kwargs["exif"] = ex.tobytes()
            except Exception:
                pass

            tmp_dst = new_tmp()
            try:
                im.save(tmp_dst, format=fmt.upper() if fmt != "jpeg" else "JPEG", **save_kwargs)
            except TypeError:
                # 某些 Pillow 版本不接受个别参数
                safe = {k: v for k, v in save_kwargs.items() if k in ("quality", "lossless")}
                im.save(tmp_dst, format=fmt.upper() if fmt != "jpeg" else "JPEG", **safe)

        new_size = tmp_dst.stat().st_size

        # "仅更小才替换" 模式
        if opts.also_smaller_only and item.src_size and new_size >= item.src_size:
            tmp_dst.unlink(missing_ok=True)
            release_reserved_path(dst)
            item.status = "跳过"
            item.dst_size = item.src_size
            item.message = f"原文件更小({human_size(item.src_size)}), 已保留原图"
            return item

        os.replace(tmp_dst, dst)
        item.dst = str(dst)
        item.dst_size = new_size
        ratio = ""
        if item.src_size:
            delta = (new_size - item.src_size) / item.src_size * 100.0
            ratio = f" ({delta:+.0f}%)"
        item.status = "完成"
        item.message = f"{human_size(item.src_size)} → {human_size(new_size)}{ratio}"
        return item

    except Exception as exc:  # noqa: BLE001
        # 失败时清理临时文件并归还名字, 避免留下垃圾 / 后续任务无法复用
        try:
            if tmp_holder["path"]:
                Path(tmp_holder["path"]).unlink(missing_ok=True)
        except Exception:
            pass
        release_reserved_path(dst)
        item.status = "失败"
        item.message = f"{type(exc).__name__}: {exc}"
        return item


def collect_files(inputs: list[Path], recursive: bool = True) -> list[Item]:
    """把输入(文件或文件夹)展开成待转换图片列表, 自动去重。"""
    items: list[Item] = []
    seen: set[str] = set()

    def add(p: Path, rel: str):
        key = str(p.resolve()).lower()
        if key in seen:
            return
        seen.add(key)
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        items.append(Item(src=p, rel=rel, src_size=size))

    for raw in inputs:
        p = Path(raw)
        if p.is_dir():
            it = p.rglob("*") if recursive else p.glob("*")
            for f in sorted(it):
                if f.is_file() and is_image_file(f):
                    try:
                        rel = str(f.parent.relative_to(p))
                    except ValueError:
                        rel = ""
                    if rel == ".":
                        rel = ""
                    add(f, rel)
        elif p.is_file():
            add(p, "")
        elif not p.exists():
            # 允许通配符
            import glob as _glob
            for g in sorted(_glob.glob(str(raw), recursive=recursive)):
                gp = Path(g)
                if gp.is_file() and is_image_file(gp):
                    add(gp, "")
    return items


def run_batch(items: list[Item], opts: Options, out_root: Path | None,
              progress=None, should_stop=None) -> Result:
    """并发批量转换。progress(done, total, item) 会在每张图完成后被调用。

    out_root 传 None 表示原地输出(写在每张原图旁边)。
    """
    res = Result()
    total = len(items)
    if total == 0:
        return res

    workers = opts.workers or min(8, max(1, (os.cpu_count() or 4)))
    workers = max(1, min(workers, total))

    done = 0
    lock = threading.Lock()
    t0 = time.time()

    def work(it: Item) -> Item:
        if should_stop and should_stop():
            it.status = "跳过"
            it.message = "已取消"
            return it
        return convert_one(it, opts, out_root)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for it in pool.map(work, items):
            with lock:
                done += 1
                if it.status == "完成":
                    res.ok += 1
                    res.src_bytes += it.src_size
                    res.dst_bytes += it.dst_size
                elif it.status == "跳过":
                    res.skipped += 1
                    res.dst_bytes += (it.dst_size or it.src_size)
                    res.src_bytes += it.src_size
                else:
                    res.failed += 1
                    res.errors.append((str(it.src), it.message))
                if progress:
                    try:
                        progress(done, total, it)
                    except Exception:
                        pass

    res.elapsed = time.time() - t0
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
    running = {"flag": False, "stop": False}
    ui_q: "queue.Queue[tuple]" = queue.Queue()
    preview_cache: dict = {}

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
        st = "normal" if var_outmode.get() == "custom" else "disabled"
        ent_out.configure(state=st)
        btn_out.configure(state=st)

    def refresh_list(select_last=False):
        tree.delete(*tree.get_children())
        for i, it in enumerate(items):
            tag = ""
            if it.status == "完成":
                tag = "ok"
            elif it.status == "失败":
                tag = "fail"
            elif it.status == "跳过":
                tag = "skip"
            tree.insert("", "end", iid=str(i),
                        values=(str(it.src), human_size(it.src_size),
                                (it.message if it.message else it.status)),
                        tags=(tag,) if tag else ())
        if select_last and items:
            tree.see(str(len(items) - 1))
        update_stat()

    def totals():
        total_src = sum(i.src_size for i in items)
        done_src = sum(i.src_size for i in items if i.status in ("完成", "跳过") and i.src_size)
        done_dst = sum((i.dst_size or 0) for i in items if i.status in ("完成", "跳过"))
        return len(items), total_src, done_src, done_dst

    def update_stat():
        n, ts, ds, dd = totals()
        done = sum(1 for i in items if i.status in ("完成", "跳过"))
        fail = sum(1 for i in items if i.status == "失败")
        txt = f"共 {n} 张 · 已完成 {done}"
        if fail:
            txt += f" · 失败 {fail}"
        if ds:
            save = (1 - dd / ds) * 100.0 if ds else 0
            txt += f" · {human_size(ds)} → {human_size(dd)} (省 {save:.0f}%)"
        elif ts:
            txt += f" · 合计 {human_size(ts)}"
        lbl_stat.configure(text=txt)

    def add_files():
        paths = filedialog.askopenfilenames(
            title="选择图片",
            filetypes=[("图片文件", " ".join(f"*{e}" for e in sorted(READ_EXTS))),
                       ("所有文件", "*.*")])
        if paths:
            add_paths([Path(p) for p in paths])

    def add_dir():
        d = filedialog.askdirectory(title="选择文件夹")
        if d:
            add_paths([Path(d)])

    def add_paths(paths: list[Path]):
        var_status.set("正在扫描文件…")
        root.update_idletasks()
        found = collect_files(paths, recursive=var_recursive.get())
        have = {str(i.src) for i in items}
        new = [f for f in found if str(f.src) not in have]
        items.extend(new)
        refresh_list(select_last=True)
        if not new:
            var_status.set(f"没有新增图片(扫描到 {len(found)} 个，可能已在列表中)")
        else:
            var_status.set(f"已添加 {len(new)} 张图片" + (f"，忽略重复 {len(found) - len(new)} 张" if len(found) != len(new) else ""))

    def remove_selected():
        sel = sorted((int(i) for i in tree.selection()), reverse=True)
        for i in sel:
            if 0 <= i < len(items):
                items.pop(i)
        refresh_list()
        var_status.set(f"已移除 {len(sel)} 项")

    def clear_all():
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

    def do_preview():
        prev_job["id"] = None
        if Image is None or ImageTk is None:
            return
        sel = tree.selection()
        canvas.delete("all")
        if not sel:
            lbl_prev_info.configure(text="选中左侧图片即可预览")
            return
        try:
            it = items[int(sel[0])]
        except (IndexError, ValueError):
            return
        try:
            with Image.open(it.src) as im:
                w0, h0 = im.size
                im = im.convert("RGBA") if im.mode in ("P", "LA") else im
                thumb = im.copy()
                thumb.thumbnail((900, 900))
                # 估计压缩后大小
                est = ""
                try:
                    import io as _io
                    buf = _io.BytesIO()
                    fmt = OUT_FORMATS.get(var_fmt.get(), ("webp", ".webp"))[0]
                    if var_lossless.get() and fmt == "webp":
                        thumb.save(buf, "WEBP", lossless=True, method=4)
                    elif fmt == "webp":
                        thumb.save(buf, "WEBP", quality=int(var_quality.get()), method=4)
                    else:
                        thumb.save(buf, fmt.upper(), quality=int(var_quality.get()))
                    est_bytes = buf.tell()
                    # 按比例换算回原尺寸的粗略估计
                    px_src = float(w0 * h0) or 1.0
                    px_th = float(thumb.width * thumb.height) or 1.0
                    est_bytes = int(est_bytes * (px_src / px_th))
                    est = f"　预估体积 ≈ {human_size(est_bytes)}"
                except Exception:
                    est = ""
                canvas_img = ImageTk.PhotoImage(thumb)
                preview_cache["img"] = canvas_img
                cw = max(canvas.winfo_width(), 10)
                ch = max(canvas.winfo_height(), 10)
                canvas.create_image(cw // 2, ch // 2, image=canvas_img, anchor="center")
                lbl_prev_info.configure(
                    text=f"{it.src.name}\n尺寸 {w0}×{h0}　原始大小 {human_size(it.src_size)}{est}")
        except Exception as exc:
            canvas.create_text(10, 10, anchor="nw", fill="#ffb4b4",
                               text=f"无法预览:\n{exc}")

    # ---- 转换 ----
    def build_options() -> Options:
        fmt, ext = OUT_FORMATS.get(var_fmt.get(), ("webp", ".webp"))
        try:
            me = int(str(var_maxedge.get()).strip() or "0")
        except ValueError:
            me = 0
        return Options(
            quality=int(var_quality.get()),
            lossless=bool(var_lossless.get()),
            out_fmt=fmt,
            out_ext=ext,
            keep_structure=bool(var_keep.get()),
            overwrite=bool(var_overwrite.get()),
            flatten=bool(var_flatten.get()),
            bg=var_bg.get() or "#ffffff",
            max_edge=max(0, me),
            also_smaller_only=bool(var_smaller_only.get()),
            recursive=bool(var_recursive.get()),
        )

    def resolve_out_root() -> Path | None:
        """返回输出根目录; None 表示"就在原图旁边"。"""
        if var_outmode.get() == "custom":
            d = Path(var_outdir.get().strip())
            if not str(d):
                raise ValueError("请先选择输出文件夹")
            d.mkdir(parents=True, exist_ok=True)
            return d
        return None

    def start():
        if running["flag"]:
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

        todo = [i for i in items if i.status != "完成"]
        if not todo:
            if not messagebox.askyesno(APP_NAME, "所有图片都已转换完成，要重新转换一遍吗？"):
                return
            todo = list(items)
        for i in todo:
            i.status = "等待"
            i.message = ""
        refresh_list()

        running["flag"] = True
        running["stop"] = False
        btn_run.configure(state="disabled")
        btn_stop.configure(state="normal")
        var_progress.set(0.0)

        def worker():
            try:
                total = len(todo)

                def prog(done, tot, it):
                    ui_q.put(("row", it))
                    ui_q.put(("prog", done, tot))

                # out_root=None 时 convert_one 会把结果写到每张原图旁边
                res = run_batch(todo, opts, out_root, progress=prog,
                                should_stop=lambda: running["stop"])
                ui_q.put(("done", res, total))
            except Exception:
                ui_q.put(("error", traceback.format_exc()))

        threading.Thread(target=worker, daemon=True).start()
        pump()

    def pump():
        try:
            while True:
                msg = ui_q.get_nowait()
                kind = msg[0]
                if kind == "row":
                    it = msg[1]
                    for idx, cand in enumerate(items):
                        if cand is it or (cand.src == it.src):
                            try:
                                tag = {"完成": "ok", "失败": "fail", "跳过": "skip"}.get(it.status, "")
                                tree.item(str(idx), values=(str(it.src), human_size(it.src_size),
                                                            it.message or it.status),
                                          tags=(tag,) if tag else ())
                            except Exception:
                                pass
                            break
                    update_stat()
                elif kind == "prog":
                    done, tot = msg[1], msg[2]
                    var_progress.set(done / max(1, tot) * 100.0)
                    var_status.set(f"正在转换 {done}/{tot} …")
                elif kind == "done":
                    res, total = msg[1], msg[2]
                    running["flag"] = False
                    btn_run.configure(state="normal")
                    btn_stop.configure(state="disabled")
                    var_progress.set(100.0)
                    verb = "已取消" if running["stop"] else "完成"
                    summary = (f"{verb} · 成功 {res.ok} · 跳过 {res.skipped} · 失败 {res.failed} · "
                               f"耗时 {res.elapsed:.1f}s")
                    if res.src_bytes:
                        save = (1 - res.dst_bytes / res.src_bytes) * 100.0
                        summary += f" · {human_size(res.src_bytes)} → {human_size(res.dst_bytes)} (省 {save:.0f}%)"
                    var_status.set(summary)
                    refresh_list()
                    var_status.set(summary)
                    if res.errors:
                        detail = "\n".join(f"· {Path(p).name}: {m}" for p, m in res.errors[:12])
                        if len(res.errors) > 12:
                            detail += f"\n… 另有 {len(res.errors) - 12} 个失败"
                        messagebox.showwarning(APP_NAME, f"有 {res.failed} 张图片转换失败:\n\n{detail}")
                    return
                elif kind == "error":
                    running["flag"] = False
                    btn_run.configure(state="normal")
                    btn_stop.configure(state="disabled")
                    var_status.set("发生错误")
                    messagebox.showerror(APP_NAME, msg[1][-2000:])
                    return
        except queue.Empty:
            pass
        if running["flag"]:
            root.after(80, pump)

    def stop():
        running["stop"] = True
        var_status.set("正在停止…")


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
    canvas.bind("<Configure>", lambda e: schedule_preview())

    # 设置页
    f1 = section(tab_set, "输出格式与质量")
    row = ttk.Frame(f1); row.pack(fill="x")
    ttk.Label(row, text="格式", width=10).pack(side="left")
    cmb_fmt = ttk.Combobox(row, textvariable=var_fmt, values=list(OUT_FORMATS.keys()),
                           state="readonly", width=18)
    cmb_fmt.pack(side="left")
    row2 = ttk.Frame(f1); row2.pack(fill="x", pady=(8, 0))
    ttk.Label(row2, text="质量", width=10).pack(side="left")
    scale = ttk.Scale(row2, from_=1, to=100, variable=var_quality,
                      command=lambda v: (var_quality.set(int(float(v))), update_q_label()))
    scale.pack(side="left", fill="x", expand=True)
    lbl_q = ttk.Label(row2, text="80", width=4)
    lbl_q.pack(side="left", padx=(6, 0))
    ttk.Checkbutton(f1, text="无损模式(文件更大，但画质 100% 保留)",
                    variable=var_lossless).pack(anchor="w", pady=(8, 0))
    ttk.Checkbutton(f1, text="智能模式：若转换后反而更大就保留原图（推荐，避免二次压缩变差）",
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
    ttk.Checkbutton(f2, text="覆盖已存在的同名文件(默认自动改名，绝不丢文件)",
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
    update_outdir_state()
    update_q_label()
    refresh_list()

    # 快捷键
    root.bind("<Control-o>", lambda e: add_files())
    root.bind("<Control-O>", lambda e: add_files())
    root.bind("<Delete>", lambda e: remove_selected())
    root.bind("<F5>", lambda e: start())
    root.bind("<Control-u>", lambda e: show_about_safe())
    root.bind("<Control-U>", lambda e: show_about_safe())

    # 拖拽
    dropped = enable_windows_drop(root, lambda files: add_paths([Path(f) for f in files]))
    if not dropped:
        var_status.set("提示: 也可直接点「添加图片」/「添加文件夹」选择文件")

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
    p.add_argument("--lossless", action="store_true", help="无损编码(体积更大)")
    p.add_argument("--keep", action="store_true", help="保留子文件夹结构")
    p.add_argument("--overwrite", action="store_true", help="覆盖同名文件")
    p.add_argument("--flatten", action="store_true", help="透明区域填充背景色")
    p.add_argument("--bg", default="#ffffff", help="填充背景色(默认 #ffffff)")
    p.add_argument("--max-edge", type=int, default=0, help="限制最长边像素(0=不缩放)")
    p.add_argument("--smaller-only", action="store_true", help="仅当结果更小才写入")
    p.add_argument("--no-recursive", action="store_true", help="不递归子文件夹")
    p.add_argument("-j", "--workers", type=int, default=0, help="并发线程数(默认自动)")
    p.add_argument("--json", action="store_true", help="输出 JSON 结果")
    p.add_argument("-v", "--version", action="version", version=f"{APP_NAME} {APP_VERSION}")
    return p


def run_cli(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.input:
        parser.print_help()
        return 2

    fmt = "jpeg" if args.format == "jpg" else args.format
    ext = {"webp": ".webp", "png": ".png", "jpeg": ".jpg", "avif": ".avif"}[fmt]
    opts = Options(
        quality=max(1, min(100, args.quality)),
        lossless=args.lossless,
        out_fmt=fmt,
        out_ext=ext,
        keep_structure=args.keep,
        overwrite=args.overwrite,
        flatten=args.flatten,
        bg=args.bg,
        max_edge=max(0, args.max_edge),
        also_smaller_only=args.smaller_only,
        workers=max(0, args.workers),
        recursive=not args.no_recursive,
    )

    roots = [Path(x) for x in args.input]
    items = collect_files(roots, recursive=opts.recursive)
    if not items:
        print("没有找到可转换的图片。", file=sys.stderr)
        return 1

    # out_root = None 表示原地输出(写在每张原图旁边)
    out_root = Path(args.outdir) if args.outdir else None

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
        mark = {"完成": "✓", "跳过": "–", "失败": "✗"}.get(it.status, "?")
        print(f"[{done:>4}/{total}] {mark} {it.src.name:<40.40} {it.message}")

    def do(res: Result) -> int:
        if args.json:
            print(json.dumps({
                "total": len(items), "ok": res.ok, "skipped": res.skipped,
                "failed": res.failed, "src_bytes": res.src_bytes,
                "dst_bytes": res.dst_bytes, "elapsed": round(res.elapsed, 2),
                "errors": [{"file": p, "error": m} for p, m in res.errors],
            }, ensure_ascii=False, indent=2))
        else:
            print("-" * 64)
            line = (f"完成: 成功 {res.ok} · 跳过 {res.skipped} · 失败 {res.failed} · "
                    f"耗时 {res.elapsed:.1f}s")
            if res.src_bytes:
                save = (1 - res.dst_bytes / res.src_bytes) * 100.0
                line += f"\n体积: {human_size(res.src_bytes)} → {human_size(res.dst_bytes)} (省 {save:.1f}%)"
            print(line)
            for p, m in res.errors[:20]:
                print(f"  ! {p}: {m}", file=sys.stderr)
        return 0 if res.failed == 0 else 3

    res = run_batch(items, opts, out_root, progress=prog)
    return do(res)


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def run_selftest() -> int:
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
    if len(sys.argv) > 2:
        targets.append(Path(sys.argv[2]))
    if getattr(sys, "frozen", False):
        targets.append(Path(sys.executable).parent / f"{APP_NAME}_自检结果.txt")
    targets.append(Path.home() / f"{APP_NAME}_自检结果.txt")

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


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if "--selftest" in argv:
            return run_selftest()
        if "--cli" in argv or "-i" in argv or "--input" in argv:
            return run_cli(argv)
        if argv and any(a in ("-h", "--help", "-v", "--version") for a in argv):
            return run_cli(argv)
        return launch_gui()
    except Exception:
        fatal_console_hint()
        if sys.stderr is not None:
            traceback.print_exc()
        try:
            import tkinter.messagebox as mb
            mb.showerror(APP_NAME, "程序发生错误:\n\n" + traceback.format_exc()[-1500:])
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
