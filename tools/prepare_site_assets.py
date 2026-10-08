"""Prepare self-hosted demo photographs and record actual encoding sizes.

Development-only helper: pip install pillow. Production Pages builds need no Pillow.
Photography is licensed by Unsplash; see site/assets/NOTICE.md.
"""
from io import BytesIO
import argparse
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "site" / "assets"
PHOTOS = (
    ("alpine", "山野", "photo-1464822759023-fed622ff2c3b"),
    ("ocean", "海岸", "photo-1518837695005-2083093ee35b"),
    ("forest", "森林", "photo-1441974231531-c6227db76b6e"),
)


def prepare_fonts():
    """Self-host open fonts; this optional development step never runs on Pages."""
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    # Include Chinese body copy, installation help and runtime status/error text.
    # One family across the UI avoids platform-dependent mixed Chinese typography.
    texts = html + "".join(path.read_text(encoding="utf-8") for path in (ROOT / "site").glob("*.js"))
    characters = "".join(sorted({char for char in texts if
        0x2000 <= ord(char) <= 0x206F or 0x2E80 <= ord(char) <= 0x9FFF or 0xFF00 <= ord(char) <= 0xFFEF}))
    sources = (
        ("manrope-latin.woff2", "Manrope:wght@200..800", "", "manrope"),
        ("heading-sc.woff2", "Noto+Sans+SC:wght@400..900", characters, "notosanssc"),
    )
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"}
    for filename, family, subset, license_folder in sources:
        url = "https://fonts.googleapis.com/css2?family=" + family + "&display=swap"
        if subset:
            url += "&text=" + urllib.parse.quote(subset)
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as response:
            css = response.read().decode()
        if not subset:
            css = css.split("/* latin */")[-1]
        font_url = re.findall(r"url\(([^)]+)\)", css)[-1]
        with urllib.request.urlopen(urllib.request.Request(font_url, headers=headers), timeout=30) as response:
            font = response.read()
        if not font.startswith(b"wOF2"):
            raise ValueError("Google Fonts did not return a WOFF2 font")
        (OUT / filename).write_bytes(font)
        license_url = f"https://raw.githubusercontent.com/google/fonts/main/ofl/{license_folder}/OFL.txt"
        with urllib.request.urlopen(license_url, timeout=30) as response:
            license_text = response.read().decode("utf-8")
            license_text = "\n".join(line.rstrip() for line in license_text.splitlines()) + "\n"
            (OUT / f"{license_folder}-OFL.txt").write_text(license_text, encoding="utf-8")
        print(filename, len(font), "bytes")


def prepare_cover():
    """Compose a social preview using our existing photograph and typography."""
    paper, ink, lime = "#f5f5ef", "#242620", "#d4ed70"
    cover = Image.new("RGB", (1200, 630), paper)
    draw = ImageDraw.Draw(cover)
    font_dir = Path("C:/Windows/Fonts")
    # The website itself uses the licensed, bundled fonts. This preview is an
    # optional authoring asset and can be regenerated on Windows with Pillow.
    if not (font_dir / "msyhbd.ttc").exists():
        with Image.open(OUT / "alpine.webp") as image:
            ImageOps.fit(image, (1200, 630)).save(OUT / "social-cover.jpg", quality=90)
        return
    heading = ImageFont.truetype(str(font_dir / "msyhbd.ttc"), 74)
    label = ImageFont.truetype(str(font_dir / "msyh.ttc"), 20)
    brand = ImageFont.truetype(str(font_dir / "segoeuib.ttf"), 32)
    draw.text((64, 49), "WebPForge.", font=brand, fill=ink)
    draw.text((62, 173), "好画质，", font=heading, fill=ink)
    draw.rectangle((61, 318, 227, 357), fill=lime)
    draw.text((62, 272), "轻装上阵。", font=heading, fill=ink)
    draw.text((66, 442), "免费 · 开源 · 离线图片转换", font=label, fill="#758260")
    draw.text((66, 482), "Windows + macOS", font=label, fill="#758260")
    with Image.open(OUT / "alpine.webp") as image:
        photograph = ImageOps.fit(image, (474, 354)).convert("RGBA")
    card = Image.new("RGBA", (496, 415), "white")
    card.paste(photograph, (11, 11))
    card_draw = ImageDraw.Draw(card)
    card_draw.text((23, 373), "alpine.webp", font=label, fill=ink)
    card_draw.text((363, 373), "285 KB", font=label, fill=ink)
    card = card.rotate(-6, resample=Image.Resampling.BICUBIC, expand=True)
    cover.paste(card, (613, 122), card)
    draw = ImageDraw.Draw(cover)
    draw.ellipse((1008, 90, 1142, 224), fill=lime, outline=paper, width=5)
    number = ImageFont.truetype(str(font_dir / "segoeuib.ttf"), 40)
    draw.text((1032, 125), "61%", font=number, fill=ink)
    draw.text((1037, 177), "更轻", font=label, fill=ink)
    cover.save(OUT / "social-cover.jpg", "JPEG", quality=90, optimize=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fonts", action="store_true", help="Download and subset the licensed website fonts")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    samples = []
    for name, label, identifier in PHOTOS:
        source = OUT / f"{name}-original.jpg"
        url = f"https://images.unsplash.com/{identifier}?fm=jpg&fit=crop&w=1600&h=1200&q=95"
        if not source.exists():
            request = urllib.request.Request(url, headers={"User-Agent": "WebPForge-Website/1.0"})
            with urllib.request.urlopen(request, timeout=40) as response:
                data = response.read()
            with Image.open(BytesIO(data)) as image:
                image.convert("RGB").save(source, "JPEG", quality=95, optimize=True)
        target = OUT / f"{name}.webp"
        thumb = OUT / f"{name}-thumb.webp"
        with Image.open(source) as image:
            image.save(target, "WEBP", quality=80, method=6)
            ImageOps.fit(image, (96, 72)).save(thumb, "WEBP", quality=75)
            width, height = image.size
        sample = dict(id=name, label=label, source=f"assets/{source.name}",
                      preview=f"assets/{target.name}", thumbnail=f"assets/{thumb.name}",
                      sourceBytes=source.stat().st_size, outputBytes=target.stat().st_size,
                      width=width, height=height, quality=80, credit=url)
        samples.append(sample)
        print(name, sample["sourceBytes"], "->", sample["outputBytes"],
              f"({round((1-sample['outputBytes']/sample['sourceBytes'])*100)}% smaller)")
    (OUT / "samples.json").write_text(json.dumps(samples, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with Image.open(ROOT / "assets" / "icon.png") as icon:
        icon.resize((48, 48), Image.Resampling.LANCZOS).save(OUT / "favicon.png")
    with Image.open(OUT / "alpine-original.jpg") as image:
        image.resize((960, 720), Image.Resampling.LANCZOS).save(OUT / "alpine-hero.webp", "WEBP", quality=83, method=6)
    prepare_cover()
    if args.fonts:
        prepare_fonts()


if __name__ == "__main__":
    main()
