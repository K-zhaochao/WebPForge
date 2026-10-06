#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""枚举系统所有顶层窗口, 找出属于指定进程名/标题的窗口。用于验证打包后的界面。"""
import ctypes
import sys
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
user32.EnumWindows.restype = wintypes.BOOL
user32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM),
                               wintypes.LPARAM]
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]

# 打开进程查询权限
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


def proc_name(pid: int) -> str:
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return "?"
    try:
        buf = ctypes.create_unicode_buffer(32768)
        size = wintypes.DWORD(32768)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value
    finally:
        kernel32.CloseHandle(h)
    return "?"


needle = sys.argv[1].lower() if len(sys.argv) > 1 else ""
rows = []


@ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
def cb(hwnd, lparam):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    cls = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, cls, 256)
    name = proc_name(pid.value)
    title = buf.value
    if needle and needle not in title.lower() and needle not in name.lower():
        return True
    if not title and not needle:
        return True
    rows.append((pid.value, name, int(hwnd), bool(user32.IsWindowVisible(hwnd)), cls.value, title))
    return True


user32.EnumWindows(cb, 0)
print(f"{'PID':<8} {'可见':<5} {'类名':<20} {'窗口标题'}")
print("-" * 100)
for pid, name, hwnd, vis, cls, title in rows:
    print(f"{pid:<8} {str(vis):<5} {cls:<20} {title}")
    print(f"{'':<8} 程序: {name}")
if not rows:
    print("(未找到匹配窗口)")
