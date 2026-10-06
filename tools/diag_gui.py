#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""诊断: 启动一个和正式界面等价的窗口, 并枚举本进程所有顶层窗口。

用于确认窗口到底有没有创建、是否可见、标题是什么。
"""
import ctypes
import sys
import threading
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tkinter as tk  # noqa: E402
from tkinter import ttk  # noqa: E402

user32 = ctypes.windll.user32
user32.EnumWindows.restype = wintypes.BOOL
user32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM),
                               wintypes.LPARAM]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]


def enum_my_windows():
    pid = ctypes.windll.kernel32.GetCurrentProcessId()
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, lparam):
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value == pid:
            n = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            cls = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(hwnd, cls, 256)
            found.append({
                "hwnd": int(hwnd),
                "visible": bool(user32.IsWindowVisible(hwnd)),
                "title": buf.value,
                "class": cls.value,
            })
        return True

    user32.EnumWindows(cb, 0)
    return found


result = {"done": False}


def build_and_report():
    from webp_converter import enable_windows_drop, launch_gui  # noqa

    # 完全等价地创建一个窗口(但不用 launch_gui, 以便自己控制生命周期)
    root = tk.Tk()
    root.title("WebPForge · 批量图片格式转换  v1.0.0")
    root.geometry("1120x760")
    style = ttk.Style()
    try:
        style.theme_use("vista")
    except Exception:
        style.theme_use("clam")
    ttk.Label(root, text="诊断窗口").pack(padx=20, pady=20)
    ttk.Button(root, text="按钮").pack()
    root.update_idletasks()
    root.update()

    print("=== tkinter 侧信息 ===")
    print("  winfo_id()   :", root.winfo_id())
    print("  winfo_viewable:", root.winfo_viewable())
    print("  winfo_ismapped:", root.winfo_ismapped())
    print("  geometry     :", root.winfo_geometry())

    hwnd_root = user32.GetAncestor(root.winfo_id(), 2)
    print("  GetAncestor(GA_ROOT):", hwnd_root)

    print("\n=== 本进程的所有顶层窗口 ===")
    for w in enum_my_windows():
        print(f"  hwnd={w['hwnd']:<10} visible={w['visible']!s:<5} class={w['class']:<18} title={w['title']!r}")

    print("\n=== 挂载拖拽支持 ===")
    ok = enable_windows_drop(root, lambda files: print("  拖入:", files))
    print("  enable_windows_drop ->", ok)
    root.update()
    known = {w["hwnd"] for w in enum_my_windows()}
    print("  挂载后窗口仍然存在:", bool(known))
    for w in enum_my_windows():
        print(f"  hwnd={w['hwnd']:<10} visible={w['visible']!s:<5} title={w['title']!r}")

    print("\n=== 5 秒后自动关闭 ===")
    sys.stdout.flush()
    root.after(5000, root.destroy)
    root.mainloop()
    result["done"] = True
    print("窗口正常关闭, 未崩溃")


t = threading.Thread(target=build_and_report, daemon=True)
t.start()
t.join(timeout=30)
print("\n结论: " + ("界面流程完整跑通" if result["done"] else "!!! 界面流程未跑完(可能卡住或崩溃)"))
