#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 把各平台构建产物整理成可直接下载的发布资源。
#
# 由 .github/workflows/build.yml 的 release 作业调用:
#     ./tools/package_release.sh <artifacts目录> <输出目录> <版本号>
#
# 之所以单独放一个脚本, 是为了能在本地用真实产物直接跑一遍 ——
# 打包步骤曾因环境差异在 CI 上反复失败, 放在这里便于本地复现与验证。
#
# 需要的环境: bash + zip(macOS 的 .app 必须用 zip 打包, 否则丢符号链接与执行权限)
# ---------------------------------------------------------------------------
set -euo pipefail

ARTIFACTS_DIR="${1:-artifacts}"
OUT_DIR="${2:-out}"
VERSION="${3:-0.0.0}"

log() { echo "[package] $*"; }
die() { echo "[package][错误] $*" >&2; exit 1; }

command -v zip >/dev/null 2>&1 || die "缺少 zip 命令, 无法打包"

[ -d "$ARTIFACTS_DIR" ] || die "找不到产物目录: $ARTIFACTS_DIR"

log "版本号   : $VERSION"
log "产物目录 : $ARTIFACTS_DIR"
log "输出目录 : $OUT_DIR"

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------
WIN="$ARTIFACTS_DIR/WebPForge-Windows-x64"
if [ -f "$WIN/WebPForge.exe" ]; then
    rm -rf stage-win
    mkdir -p stage-win
    cp "$WIN/WebPForge.exe" stage-win/

    # 说明文档优先取产物里的, 没有就回退到仓库根目录
    for extra in README.md README.en.md LICENSE convert.bat; do
        if [ -f "$WIN/$extra" ]; then
            cp "$WIN/$extra" stage-win/
        elif [ -f "$extra" ]; then
            cp "$extra" stage-win/
        else
            log "提示: $extra 未找到, 跳过"
        fi
    done

    ( cd stage-win && zip -r -q "../$OUT_DIR/WebPForge-${VERSION}-Windows-x64.zip" . )
    log "已生成 WebPForge-${VERSION}-Windows-x64.zip"
else
    die "缺少 Windows 产物: $WIN/WebPForge.exe 不存在"
fi

# ---------------------------------------------------------------------------
# macOS (必须压缩, 否则 .app 的权限与符号链接会丢失)
#   自动流程只产出 ARM64; Intel 由 build-intel.yml 手动构建, 有就一起打进来
# ---------------------------------------------------------------------------
mac_count=0
for arch in ARM64 Intel; do
    SRC="$ARTIFACTS_DIR/WebPForge-macOS-${arch}/WebPForge.app"
    if [ -d "$SRC" ]; then
        rm -rf "stage-mac-$arch"
        mkdir -p "stage-mac-$arch"
        cp -R "$SRC" "stage-mac-$arch/"
        for extra in README.md README.en.md LICENSE; do
            [ -f "$extra" ] && cp "$extra" "stage-mac-$arch/"
        done
        ( cd "stage-mac-$arch" && \
          zip -r -q --symlinks "../$OUT_DIR/WebPForge-${VERSION}-macOS-${arch}.zip" . )
        log "已生成 WebPForge-${VERSION}-macOS-${arch}.zip"
        mac_count=$((mac_count + 1))
    else
        log "没有 macOS-${arch} 产物, 跳过"
    fi
done

[ "$mac_count" -gt 0 ] || die "没有任何 macOS 产物, 中止发布"

# ---------------------------------------------------------------------------
# 结果
# ---------------------------------------------------------------------------
log "打包完成, 产出如下:"
ls -lh "$OUT_DIR"

count=$(find "$OUT_DIR" -name '*.zip' | wc -l)
[ "$count" -gt 0 ] || die "输出目录里没有任何 zip"
log "共 $count 个发布资源"
