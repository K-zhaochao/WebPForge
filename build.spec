# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置 —— WebPForge

构建:
    pyinstaller --clean --noconfirm build.spec

产物:
    Windows: dist/WebPForge.exe            (单文件)
    macOS  : dist/WebPForge                (可执行文件, 由 build_macos.sh 组装成 .app)
"""
import sys
from pathlib import Path

ROOT = Path(SPECPATH).resolve()
if not (ROOT / "webp_converter.py").exists():
    ROOT = Path.cwd()

ENTRY = str(ROOT / "webp_converter.py")
APP_NAME = "WebPForge"

ICON = None
if sys.platform.startswith("win"):
    ico = ROOT / "assets" / "icon.ico"
    if ico.exists():
        ICON = ico
else:
    icns = ROOT / "assets" / "icon.icns"
    if icns.exists():
        ICON = icns
    elif (ROOT / "assets" / "icon.png").exists():
        ICON = ROOT / "assets" / "icon.png"

VERSION_FILE = ROOT / "version_info.txt"
VERSION = str(VERSION_FILE) if (VERSION_FILE.exists() and sys.platform.startswith("win")) else None

# 这些库体积大且用不到, 明确排除以缩小体积
EXCLUDES = [
    "numpy", "pandas", "matplotlib", "scipy", "sympy", "IPython", "notebook",
    "pytest", "setuptools", "pip", "wheel", "pydoc_data", "test", "unittest",
    "xmlrpc", "http.server", "sqlite3", "curses", "distutils", "lib2to3",
    "PIL.ImageQt", "PyQt5", "PyQt6", "PySide2", "PySide6", "wx",
]

HIDDEN = []
try:
    from PIL import features as _f  # noqa
    HIDDEN += ["PIL._webp", "PIL._imaging", "PIL.WebPImagePlugin",
               "PIL.PngImagePlugin", "PIL.JpegImagePlugin", "PIL.GifImagePlugin",
               "PIL.BmpImagePlugin", "PIL.TiffImagePlugin", "PIL.IcoImagePlugin",
               "PIL.AvifImagePlugin", "PIL.Image", "PIL.ImageOps", "PIL.ImageTk"]
except Exception:
    pass

a = Analysis(
    [ENTRY],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                 # 双击运行时不弹黑色控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,              # macOS 上可设 'universal2' 生成 Intel+ARM 通用包
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON) if ICON else None,
    version=VERSION,               # 仅 Windows: exe 属性里的版本信息
)
