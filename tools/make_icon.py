#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成应用图标: 深色圆角底 + 图层/箭头意象, 输出 .ico (Windows) 与 .png (macOS)。

用法: python tools/make_icon.py <输出目录>
"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "assets")
OUT.mkdir(parents=True, exist_ok=True)

# 主色: 蓝紫 -> 青色渐变感的 WebP 工具配色
BG_TOP = (32, 44, 74)
BG_BOT = (18, 24, 42)
ACCENT = (58, 190, 214)     # 青
ACCENT2 = (120, 132, 255)   # 紫蓝
WHITE = (245, 248, 255)


def rounded_mask(size: int, radius_ratio: float = 0.22) -> Image.Image:
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    r = int(size * radius_ratio)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=r, fill=255)
    return m


def vertical_gradient(size: int, top, bot) -> Image.Image:
    g = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / max(1, size - 1)
        g.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    return g.resize((size, size), Image.NEAREST)


def render(size: int) -> Image.Image:
    ss = 4  # 超采样, 边缘更干净
    S = size * ss
    img = vertical_gradient(S, BG_TOP, BG_BOT).convert("RGBA")

    d = ImageDraw.Draw(img)

    # 两张略微错位的"照片"卡片
    card_w, card_h = int(S * 0.46), int(S * 0.34)
    x0, y0 = int(S * 0.16), int(S * 0.22)

    # 后卡片
    d.rounded_rectangle((x0 + int(S * 0.14), y0 - int(S * 0.07),
                         x0 + int(S * 0.14) + card_w, y0 - int(S * 0.07) + card_h),
                        radius=int(S * 0.045), fill=(70, 84, 130, 190))
    # 前卡片
    d.rounded_rectangle((x0, y0, x0 + card_w, y0 + card_h),
                        radius=int(S * 0.045), fill=WHITE)
    # 卡片里的"山与太阳"
    inner = (x0 + int(S * 0.035), y0 + int(S * 0.035),
             x0 + card_w - int(S * 0.035), y0 + card_h - int(S * 0.035))
    d.ellipse((inner[0] + int(S * 0.03), inner[1] + int(S * 0.02),
               inner[0] + int(S * 0.10), inner[1] + int(S * 0.09)),
              fill=(255, 196, 84))
    d.polygon([(inner[0], inner[3]),
               (inner[0] + int(S * 0.13), inner[1] + int(S * 0.11)),
               (inner[0] + int(S * 0.24), inner[3])], fill=ACCENT2)
    d.polygon([(inner[0] + int(S * 0.10), inner[3]),
               (inner[0] + int(S * 0.22), inner[1] + int(S * 0.145)),
               (inner[2], inner[3])], fill=ACCENT)

    # 右下角的转换箭头(循环/刷新意象)
    cx, cy = int(S * 0.715), int(S * 0.705)
    r = int(S * 0.175)
    w = int(S * 0.075)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=ACCENT, width=w)
    # 箭头三角
    t = int(S * 0.085)
    d.polygon([(cx + r - int(t * 0.2), cy - r - t // 2),
               (cx + r + t, cy - r + t // 2),
               (cx + r - int(t * 0.2), cy - r + int(t * 1.3))], fill=ACCENT)
    # 中心圆点
    d.ellipse((cx - int(S * 0.045), cy - int(S * 0.045),
               cx + int(S * 0.045), cy + int(S * 0.045)), fill=WHITE)

    img = img.resize((size, size), Image.LANCZOS)
    img.putalpha(rounded_mask(size))
    return img


sizes = [16, 24, 32, 48, 64, 128, 256]
imgs = {s: render(s) for s in sizes}

png512 = render(512)
png512.save(OUT / "icon.png")
print("写出:", OUT / "icon.png")

# Windows .ico (多尺寸)
ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
imgs[256].save(OUT / "icon.ico", format="ICO", sizes=ico_sizes)
print("写出:", OUT / "icon.ico")

# macOS .icns —— 仅在 macOS 上可用 iconutil; 这里先落地 iconset 目录
iconset = OUT / "icon.iconset"
iconset.mkdir(exist_ok=True)
mapping = {
    "icon_16x16.png": 16, "icon_16x16@2x.png": 32,
    "icon_32x32.png": 32, "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128, "icon_128x128@2x.png": 256,
    "icon_256x256.png": 256, "icon_256x256@2x.png": 512,
    "icon_512x512.png": 512, "icon_512x512@2x.png": 1024,
}
for name, s in mapping.items():
    render(s).save(iconset / name)
print("写出:", iconset)
