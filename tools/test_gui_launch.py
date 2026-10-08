#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在主线程启动真实 GUI，并通过正常关闭流程退出。"""
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tkinter as tk
import webp_converter as wc

mainloop = tk.Tk.mainloop
errors = []


def smoke_test(root):
    root.withdraw()
    root.report_callback_exception = lambda kind, value, trace: errors.append(str(value))
    root.after(400, lambda: root.tk.call(root.protocol("WM_DELETE_WINDOW")))
    mainloop(root)


with patch.object(tk.Tk, "mainloop", smoke_test):
    rc = wc.launch_gui()

for error in errors:
    print(error, file=sys.stderr)
print("GUI launch and close:", "OK" if rc == 0 and not errors else "FAILED")
sys.exit(0 if rc == 0 and not errors else 1)
