#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""真实环境下生成一组测试图片(含中文名/透明/动画/超大图/损坏文件)。"""
import os, sys, random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

root = Path(sys.argv[1] if len(sys.argv) > 1 else "_testdata")
if root.exists():
    import shutil
    shutil.rmtree(root)
(root / "子文件夹" / "更深的目录").mkdir(parents=True, exist_ok=True)

random.seed(7)

def gradient(w, h, seed=0):
    im = Image.new("RGB", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(0, w, 4):
            r = (x * 255 // max(1, w) + seed * 40) % 256
            g = (y * 255 // max(1, h) + seed * 90) % 256
            b = ((x + y) * 255 // max(1, w + h) + seed * 150) % 256
            for dx in range(4):
                if x + dx < w:
                    px[x + dx, y] = (r, g, b)
    return im

# 1. 普通 JPEG
gradient(1920, 1080, 1).save(root / "photo_1920x1080.jpg", quality=92)
# 2. 中文名 JPEG
gradient(800, 600, 2).save(root / "示例照片-中文名.jpg", quality=90)
# 3. 透明 PNG
im = Image.new("RGBA", (600, 400), (0, 0, 0, 0))
d = ImageDraw.Draw(im)
d.ellipse((20, 20, 300, 260), fill=(255, 80, 80, 255))
d.rectangle((250, 150, 560, 370), fill=(40, 120, 255, 128))
im.save(root / "transparent_logo.png")
# 4. 调色板 PNG + 透明
p = Image.new("P", (200, 200))
p.putpalette([i % 256 for i in range(768)])
p.info["transparency"] = 0
p.save(root / "palette_trans.png")
# 5. BMP
gradient(320, 240, 3).save(root / "bitmap.bmp")
# 6. 动画 GIF
frames = [gradient(200, 150, i) for i in range(4)]
frames[0].save(root / "anim.gif", save_all=True, append_images=frames[1:], duration=120, loop=0)
# 7. 带 EXIF 方向标记的 JPEG (orientation=6 表示需旋转 90°)
from PIL import Image as I
rot = gradient(400, 300, 5)
ex = rot.getexif()
ex[0x0112] = 6
rot.save(root / "exif_rotated.jpg", exif=ex.tobytes(), quality=88)
# 8. 子文件夹里的图
gradient(500, 500, 6).save(root / "子文件夹" / "sub1.png")
gradient(640, 480, 7).save(root / "子文件夹" / "更深的目录" / "deep.png")
# 9. 已经很小的小图
Image.new("RGB", (32, 32), (10, 200, 10)).save(root / "tiny_icon.png")
# 10. 损坏文件 + 伪图片
(root / "broken.jpg").write_bytes(b"\xff\xd8\xff\xe0this is not a real jpeg" * 4)
(root / "notes.txt").write_text("not an image", encoding="utf-8")
# 11. 已经是 webp (重转测试)
gradient(300, 300, 9).save(root / "already.webp", quality=70)

n = sum(1 for _ in (root).rglob("*") if _.is_file())
print(f"生成完成: {root.resolve()}")
print(f"文件数: {n}")
for f in sorted(root.rglob("*")):
    if f.is_file():
        print("  ", f.relative_to(root), f.stat().st_size, "bytes")
