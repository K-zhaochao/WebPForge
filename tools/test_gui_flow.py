#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""运行真实 GUI 回归测试；自行生成临时图片，无需预先准备 _testdata。"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_gui.py")
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
