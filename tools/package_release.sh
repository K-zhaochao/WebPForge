#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 把各平台构建产物整理成可直接下载的发布资源。
#
# 由 .github/workflows/build.yml 的 release 作业调用:
#     ./tools/package_release.sh <artifacts目录> <输出目录> <版本号>
#
# 设计要点:
#   1. 不硬编码子目录名 —— 用 find 搜索产物, 兼容 download-artifact 的目录布局差异
#   2. 每一步都打印找到了什么, 失败时能直接从日志看出原因
#   3. 需要的环境: bash + zip
#      (macOS 的 .app 必须用 zip 打包, 用 Python zipfile 会丢符号链接与执行权限)
# ---------------------------------------------------------------------------
set -euo pipefail

ARTIFACTS_DIR="${1:-artifacts}"
OUT_DIR="${2:-out}"
VERSION="${3:-0.0.0}"

log() { echo "[package] $*"; }
die() { echo "[package][错误] $*" >&2; exit 1; }

command -v zip >/dev/null 2>&1 || die "缺少 zip 命令"

# 解压优先用 Python(zipfile 是标准库, 必然可用),
# 避免再依赖 unzip —— 精简的 runner 镜像并不保证装了它。
extract_zip() {
    local src="$1" dest="$2"
    if command -v python3 >/dev/null 2>&1; then
        python3 -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$src" "$dest"
    elif command -v unzip >/dev/null 2>&1; then
        unzip -q "$src" -d "$dest"
    else
        die "既没有 python3 也没有 unzip, 无法解压 $src"
    fi
}

[ -d "$ARTIFACTS_DIR" ] || die "找不到产物目录: $ARTIFACTS_DIR"

log "版本号   : $VERSION"
log "产物目录 : $ARTIFACTS_DIR"
log "输出目录 : $OUT_DIR"
log ""
log "=== 产物目录实际内容 ==="
find "$ARTIFACTS_DIR" -maxdepth 3 -printf '%y %10s  %p\n' 2>/dev/null | sort -k3 || find "$ARTIFACTS_DIR" -maxdepth 3
log ""

rm -rf "$OUT_DIR" stage-win stage-mac-ARM64 stage-mac-Intel
mkdir -p "$OUT_DIR"

# ---------------------------------------------------------------------------
# Windows: 直接搜索 exe, 不依赖具体目录层级
# ---------------------------------------------------------------------------
EXE_PATH="$(find "$ARTIFACTS_DIR" -type f -name 'WebPForge.exe' | head -1)"
[ -n "$EXE_PATH" ] || die "在 $ARTIFACTS_DIR 里找不到 WebPForge.exe"
log "找到 Windows 程序: $EXE_PATH"

WIN_DIR="$(dirname "$EXE_PATH")"
mkdir -p stage-win
cp "$EXE_PATH" stage-win/

# 说明文档优先取产物里的, 没有就回退到仓库根目录
for extra in README.md README.en.md LICENSE convert.bat; do
    if [ -f "$WIN_DIR/$extra" ]; then
        cp "$WIN_DIR/$extra" stage-win/
        log "  附带: $extra (来自产物)"
    elif [ -f "$extra" ]; then
        cp "$extra" stage-win/
        log "  附带: $extra (来自仓库)"
    else
        log "  跳过: $extra (未找到)"
    fi
done

( cd stage-win && zip -r -q "../$OUT_DIR/WebPForge-${VERSION}-Windows-x64.zip" . )
log "已生成 WebPForge-${VERSION}-Windows-x64.zip"
log ""

# ---------------------------------------------------------------------------
# macOS
#   构建端会上传 WebPForge.app.zip 而不是裸目录 —— .app 本质是目录,
#   直接上传会被展开成 Contents/, 外层 .app 名字会丢失。
#   这里解开 .app.zip 后重新打包, 顺手把说明文档一起放进去。
# ---------------------------------------------------------------------------
mac_count=0
while IFS= read -r APP_ZIP; do
    [ -n "$APP_ZIP" ] || continue

    # 从路径推断架构(ARM64 / Intel), 推断不出就标记为 Universal
    case "$APP_ZIP" in
        *ARM64*)   arch="ARM64" ;;
        *Intel*)   arch="Intel" ;;
        *)         arch="Universal" ;;
    esac

    work="unpack-$arch"
    rm -rf "$work" "stage-mac-$arch"
    mkdir -p "$work" "stage-mac-$arch"

    log "找到 macOS 包: $APP_ZIP  -> 架构 $arch"
    if ! extract_zip "$APP_ZIP" "$work"; then
        die "解压失败: $APP_ZIP"
    fi

    APP_PATH="$(find "$work" -maxdepth 2 -type d -name 'WebPForge.app' | head -1)"
    [ -n "$APP_PATH" ] || die "解压后没找到 WebPForge.app: $APP_ZIP"

    cp -R "$APP_PATH" "stage-mac-$arch/"
    for extra in README.md README.en.md LICENSE; do
        [ -f "$extra" ] && cp "$extra" "stage-mac-$arch/"
    done

    ( cd "stage-mac-$arch" && \
      zip -r -q --symlinks "../$OUT_DIR/WebPForge-${VERSION}-macOS-${arch}.zip" . )
    log "已生成 WebPForge-${VERSION}-macOS-${arch}.zip"
    mac_count=$((mac_count + 1))
done < <(find "$ARTIFACTS_DIR" -type f -name 'WebPForge.app.zip' | sort)

# 兼容: 万一是裸 .app 目录(旧布局), 也照样处理
while IFS= read -r APP_PATH; do
    [ -n "$APP_PATH" ] || continue
    case "$APP_PATH" in
        *ARM64*)   arch="ARM64" ;;
        *Intel*)   arch="Intel" ;;
        *)         arch="Universal" ;;
    esac
    log "找到 macOS 应用目录: $APP_PATH  -> 架构 $arch"
    rm -rf "stage-mac-$arch"
    mkdir -p "stage-mac-$arch"
    cp -R "$APP_PATH" "stage-mac-$arch/"
    for extra in README.md README.en.md LICENSE; do
        [ -f "$extra" ] && cp "$extra" "stage-mac-$arch/"
    done
    ( cd "stage-mac-$arch" && \
      zip -r -q --symlinks "../$OUT_DIR/WebPForge-${VERSION}-macOS-${arch}.zip" . )
    log "已生成 WebPForge-${VERSION}-macOS-${arch}.zip"
    mac_count=$((mac_count + 1))
done < <(find "$ARTIFACTS_DIR" -type d -name 'WebPForge.app' | sort)

[ "$mac_count" -gt 0 ] || die "在 $ARTIFACTS_DIR 里找不到 macOS 产物(.app.zip 或 .app 目录都没有)"
log ""

# ---------------------------------------------------------------------------
# 结果
# ---------------------------------------------------------------------------
log "=== 打包完成, 产出如下 ==="
ls -lh "$OUT_DIR"
count=$(find "$OUT_DIR" -name '*.zip' | wc -l)
[ "$count" -gt 0 ] || die "输出目录里没有任何 zip"
log "共 $count 个发布资源"
