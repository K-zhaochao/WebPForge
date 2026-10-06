#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在进程内运行真实的 launch_gui(), 几秒后自动关闭, 验证完整界面可正常创建与销毁。"""
import sys
import threading
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import webp_converter as wc  # noqa: E402

result = {"rc": None, "err": None}


def main():
    try:
        result["rc"] = wc.launch_gui()
    except BaseException:
        result["err"] = traceback.format_exc()


t = threading.Thread(target=main, daemon=True)
t.start()

# 等界面起来, 然后找到它的 Tk 实例并关闭
import time
time.sleep(6)

import tkinter as tk
roots = [w for w in tk._default_root.__class__.__mro__ and [] ] if False else None

# 通过默认 root 关闭
try:
    r = tk._default_root
    if r is not None:
        print("检测到已创建的默认 Tk root, 标题:", repr(r.title()))
        r.after(500, r.destroy)
    else:
        print("未找到默认 Tk root")
except Exception as e:
    print("关闭时异常:", e)

t.join(timeout=15)

print("-" * 50)
if result["err"]:
    print("launch_gui 抛出异常:")
    print(result["err"])
    sys.exit(1)
elif result["rc"] is None:
    print("launch_gui 未在超时内返回(可能仍在运行)")
    sys.exit(2)
else:
    print(f"launch_gui 正常返回, 返回值 = {result['rc']}")
    sys.exit(0)
