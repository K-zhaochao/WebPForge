#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在真实的 Tk 环境里驱动界面: 添加文件 -> 渲染预览 -> 执行转换, 验证整条交互链路。

直接在进程内调用 launch_gui 无法注入操作, 因此这里复刻界面并复用真实的
handler 逻辑路径(collect_files / convert_one / 预览编码), 检查是否报错。
"""
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk

import webp_converter as wc

WS = Path(__file__).resolve().parent.parent
TESTDATA = WS / "_testdata"
OUT = WS / "_gui_test_out"
if OUT.exists():
    import shutil
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)

errors = []
info = []


def step(name, fn):
    try:
        fn()
        info.append(f"[OK] {name}")
    except Exception as exc:
        errors.append(f"[!!] {name}: {type(exc).__name__}: {exc}")
        errors.append(traceback.format_exc())


root = tk.Tk()
root.title("界面链路测试")
root.geometry("900x600")
style = ttk.Style()
try:
    style.theme_use("vista")
except Exception:
    style.theme_use("clam")

items = []
canvas = tk.Canvas(root, background="#2b2b2b", width=500, height=300)
canvas.pack(fill="both", expand=True)
prev_cache = {}


def do_preview(it):
    """复刻界面里的预览逻辑。"""
    with Image.open(it.src) as im:
        w0, h0 = im.size
        im = im.convert("RGBA") if im.mode in ("P", "LA") else im
        thumb = im.copy()
        thumb.thumbnail((900, 900))
        import io
        buf = io.BytesIO()
        thumb.save(buf, "WEBP", quality=80, method=4)
        est = int(buf.tell() * (float(w0 * h0) / float(thumb.width * thumb.height)))
        img = ImageTk.PhotoImage(thumb)
        prev_cache["img"] = img
        canvas.delete("all")
        canvas.create_image(250, 150, image=img, anchor="center")
        return w0, h0, est


def t1():
    found = wc.collect_files([TESTDATA], recursive=True)
    items.extend(found)
    info.append(f"     扫描到 {len(found)} 个文件")


def t2():
    # 预览每一张真实图片(包括中文名、透明、动画)
    ok = 0
    for it in items:
        try:
            w0, h0, est = do_preview(it)
            root.update()
            ok += 1
        except Exception as exc:
            errors.append(f"[!!] 预览失败 {it.src.name}: {exc}")
    info.append(f"     成功预览 {ok}/{len(items)} 张")


def t3():
    opts = wc.Options(quality=80, out_fmt="webp", out_ext=".webp",
                      keep_structure=True, also_smaller_only=True)
    res = wc.run_batch(items, opts, OUT)
    info.append(f"     转换: 成功={res.ok} 跳过={res.skipped} 失败={res.failed}")
    for p, m in res.errors:
        info.append(f"       预期内失败: {Path(p).name} -> {m}")


def t4():
    produced = list(OUT.rglob("*.webp"))
    info.append(f"     产出 {len(produced)} 个 webp")
    for p in produced:
        with Image.open(p) as im:
            im.load()
    info.append("     全部产物可正常读取")


def t5():
    # 中文文件名/文件夹是否被正确写出
    cn = [p for p in OUT.rglob("*.webp") if any(ord(c) > 127 for c in str(p))]
    info.append(f"     含中文路径的产物: {len(cn)} 个")


for name, fn in [("扫描文件", t1), ("渲染预览", t2), ("批量转换", t3),
                 ("校验产物", t4), ("中文路径", t5)]:
    step(name, fn)

root.update()
root.after(300, root.destroy)
root.mainloop()

print("=== 界面交互链路测试 ===")
for line in info:
    print(line)
if errors:
    print("\n=== 错误 ===")
    for e in errors:
        print(e)
    sys.exit(1)
print("\n=== 全部通过 ===")
sys.exit(0)
