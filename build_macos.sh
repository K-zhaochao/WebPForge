#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 在 macOS 上打包 WebPForge
#
# 用法:
#     chmod +x build_macos.sh      # 只需执行一次
#     ./build_macos.sh
#
# 产物:
#     dist/WebPForge.app      —— 双击即可运行的应用
#     dist/WebPForge.dmg      —— 可分发的安装镜像(若可用)
#
# 说明: macOS 应用必须在 macOS 上构建, 无法在 Windows 上交叉编译。
# ---------------------------------------------------------------------------
set -euo pipefail

cd "$(dirname "$0")"
ROOT="$(pwd)"
APP_NAME="WebPForge"

# 版本号: 优先取 git tag(如 v1.2.0 -> 1.2.0), 否则用默认值
GIT_TAG="$(git describe --tags --abbrev=0 2>/dev/null || true)"
if [ -n "$GIT_TAG" ]; then
    APP_VERSION="${GIT_TAG#v}"
else
    APP_VERSION="1.0.0"
fi

echo "=============================================="
echo " 打包 $APP_NAME v$APP_VERSION (macOS)"
echo "=============================================="

# ---------- 1. 找 Python ----------
PY=""
for cand in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
    echo "✗ 没有找到 python3。"
    echo "  请先安装 Python 3.10+ :  https://www.python.org/downloads/macos/"
    exit 1
fi
echo "· 使用 Python: $($PY --version 2>&1)  ($(command -v "$PY"))"

# ---------- 2. 检查 tkinter(Python 官方安装包自带) ----------
if ! "$PY" -c "import tkinter" >/dev/null 2>&1; then
    echo "✗ 当前 Python 缺少 tkinter, 无法显示界面。"
    echo "  请改用 python.org 官方安装包(自带 tkinter),"
    echo "  或执行: brew install python-tk"
    exit 1
fi
echo "· tkinter: 可用"

# ---------- 3. 建立虚拟环境并安装依赖 ----------
VENV="$ROOT/.venv-macos"
if [ ! -d "$VENV" ]; then
    echo "· 创建虚拟环境 .venv-macos ..."
    "$PY" -m venv "$VENV"
fi
VPY="$VENV/bin/python"
echo "· 安装 Pillow 与 PyInstaller ..."
"$VPY" -m pip install --quiet --upgrade pip
"$VPY" -m pip install --quiet --upgrade pillow pyinstaller

# ---------- 4. 生成图标 .icns ----------
echo "· 生成图标 ..."
"$VPY" tools/make_icon.py assets
if command -v iconutil >/dev/null 2>&1; then
    rm -rf assets/icon.icns
    iconutil -c icns assets/icon.iconset -o assets/icon.icns
    echo "  → assets/icon.icns"
else
    echo "  ! 未找到 iconutil, 将使用默认图标"
fi

# ---------- 5. 打包 ----------
echo "· 正在打包(首次约需 1-3 分钟) ..."
rm -rf build dist
"$VPY" -m PyInstaller --clean --noconfirm \
    --distpath "$ROOT/dist" --workpath "$ROOT/build" "$ROOT/build.spec"

BIN="dist/$APP_NAME"
if [ ! -f "$BIN" ]; then
    echo "✗ 打包失败: 未生成 $BIN"
    exit 1
fi
chmod +x "$BIN"
echo "· 可执行文件: $BIN"

# ---------- 6. 组装 .app ----------
echo "· 组装 .app 应用包 ..."
APP="dist/$APP_NAME.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cp "$BIN" "$APP/Contents/MacOS/$APP_NAME"
chmod +x "$APP/Contents/MacOS/$APP_NAME"
[ -f assets/icon.icns ] && cp assets/icon.icns "$APP/Contents/Resources/icon.icns"

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>                  <string>$APP_NAME</string>
    <key>CFBundleDisplayName</key>           <string>$APP_NAME</string>
    <key>CFBundleExecutable</key>            <string>$APP_NAME</string>
    <key>CFBundleIdentifier</key>            <string>io.github.webpforge</string>
    <key>CFBundleVersion</key>               <string>$APP_VERSION</string>
    <key>CFBundleShortVersionString</key>    <string>$APP_VERSION</string>
    <key>CFBundlePackageType</key>           <string>APPL</string>
    <key>CFBundleIconFile</key>              <string>icon.icns</string>
    <key>LSMinimumSystemVersion</key>        <string>10.15</string>
    <key>NSHighResolutionCapable</key>       <true/>
    <key>LSApplicationCategoryType</key>     <string>public.app-category.graphics-design</string>
    <key>NSHumanReadableCopyright</key>      <string>MIT License</string>
</dict>
</plist>
PLIST

# 让系统刷新图标缓存
touch "$APP"

# ---------- 7. 临时签名(避免"已损坏"提示) ----------
if command -v codesign >/dev/null 2>&1; then
    codesign --force --deep --sign - "$APP" 2>/dev/null && \
        echo "· 已做临时签名(ad-hoc)" || echo "  ! 临时签名失败(不影响本机使用)"
fi

# ---------- 8. 打包成 dmg(可选) ----------
if command -v hdiutil >/dev/null 2>&1; then
    echo "· 生成 dmg ..."
    rm -f "dist/$APP_NAME.dmg"
    hdiutil create -volname "$APP_NAME" -srcfolder "$APP" -ov -format UDZO \
        "dist/$APP_NAME.dmg" >/dev/null 2>&1 && echo "  → dist/$APP_NAME.dmg" || true
fi

echo ""
echo "=============================================="
echo " 打包完成 ✓"
echo "=============================================="
echo "  应用    : dist/$APP_NAME.app    (双击运行)"
[ -f "$BIN" ] && echo "  可执行  : dist/$APP_NAME"
[ -f "dist/$APP_NAME.dmg" ] && echo "  安装镜像: dist/$APP_NAME.dmg"
echo ""
echo "提示: 若双击提示「无法打开, 因为 Apple 无法检查是否包含恶意软件」,"
echo "      请右键点击 App → 选择「打开」→ 再点「打开」即可;"
echo "      或在终端执行: xattr -cr \"dist/$APP_NAME.app\""
echo ""
