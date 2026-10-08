"""Build the dependency-free GitHub Pages site and validate its local references.

    python tools/build_site.py
    python -m http.server 4173 --bind 127.0.0.1 --directory _site

Use --refresh-release during deployment to resolve the latest complete public
release. Local builds use the checked-in release.json and need no network.
"""

import argparse
from html import escape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "site"
OUTPUT = ROOT / "_site"
SITE_URL = "https://k-zhaochao.github.io/WebPForge/"
REPOSITORY = "K-zhaochao/WebPForge"


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.references = []
        self.errors = []

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if "id" in attributes:
            identifier = attributes["id"]
            if identifier in self.ids:
                self.errors.append(f"Duplicate id: {identifier}")
            self.ids.add(identifier)
        for name in ("href", "src", "poster"):
            if attributes.get(name):
                self.references.append(attributes[name])
        if tag == "img" and "alt" not in attributes:
            self.errors.append("Image is missing its alt attribute")


def refresh_release():
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "WebPForge-Pages"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    request = urllib.request.Request(
        f"https://api.github.com/repos/{REPOSITORY}/releases/latest",
        headers=headers,
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        release = json.load(response)
    assets = release["assets"]
    result = {"tag": release["tag_name"], "url": release["html_url"]}
    for platform, suffix in (("windows", "-Windows-x64.zip"), ("macos", "-macOS-ARM64.zip")):
        matches = [asset for asset in assets if asset["name"].endswith(suffix)]
        if len(matches) != 1:
            raise ValueError(f"Latest release has no unambiguous {platform} package")
        asset = matches[0]
        result[platform] = {"url": asset["browser_download_url"], "bytes": asset["size"]}
    return result


def validate_release(release):
    prefix = f"https://github.com/{REPOSITORY}/releases/"
    if not release["url"].startswith(prefix + "tag/"):
        raise ValueError("Unexpected release URL")
    for platform in ("windows", "macos"):
        if not release[platform]["url"].startswith(prefix + "download/"):
            raise ValueError(f"Unexpected {platform} asset URL")
        if not isinstance(release[platform]["bytes"], int) or release[platform]["bytes"] <= 0:
            raise ValueError(f"Invalid {platform} asset size")


def validate_site(html):
    references = References()
    references.feed(html)
    references.close()
    for css in SOURCE.glob("*.css"):
        references.references.extend(re.findall(r"url\(['\"]?([^)'\"]+)", css.read_text(encoding="utf-8")))
    for script in SOURCE.glob("*.js"):
        references.references.extend(re.findall(r"from\s+['\"]([^'\"]+)", script.read_text(encoding="utf-8")))
    for reference in references.references:
        parsed = urllib.parse.urlsplit(reference)
        if parsed.scheme or parsed.netloc:
            if parsed.scheme not in ("https", "data", "mailto"):
                references.errors.append(f"Unexpected external scheme: {reference}")
            continue
        if not parsed.path:
            if parsed.fragment and urllib.parse.unquote(parsed.fragment) not in references.ids:
                references.errors.append(f"Missing fragment: {reference}")
            continue
        if parsed.path.startswith("/"):
            references.errors.append(f"Root-relative link breaks project Pages: {reference}")
            continue
        target = (SOURCE / urllib.parse.unquote(parsed.path)).resolve()
        if not target.is_relative_to(SOURCE.resolve()) or not target.is_file():
            references.errors.append(f"Missing or unsafe local reference: {reference}")
    for sample in json.loads((SOURCE / "assets" / "samples.json").read_text(encoding="utf-8")):
        for field, size_field in (("source", "sourceBytes"), ("preview", "outputBytes")):
            target = (SOURCE / sample[field]).resolve()
            if not target.is_relative_to(SOURCE.resolve()) or not target.is_file():
                references.errors.append(f"Missing or unsafe sample: {sample[field]}")
            elif target.stat().st_size != sample[size_field]:
                references.errors.append(f"Sample size has drifted: {sample[field]}")
        thumbnail = (SOURCE / sample["thumbnail"]).resolve()
        if not thumbnail.is_relative_to(SOURCE.resolve()) or not thumbnail.is_file():
            references.errors.append(f"Missing sample thumbnail: {sample['thumbnail']}")
    if "@@" in html:
        references.errors.append("Unresolved template tokens")
    if references.errors:
        raise ValueError("\n".join(references.errors))
    return len(references.references)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-release", action="store_true")
    args = parser.parse_args()
    release = refresh_release() if args.refresh_release else json.loads((SOURCE / "release.json").read_text(encoding="utf-8"))
    validate_release(release)
    values = {
        "SITE_URL": SITE_URL,
        "RELEASE_TAG": release["tag"],
        "RELEASE_URL": release["url"],
        "WINDOWS_URL": release["windows"]["url"],
        "MACOS_URL": release["macos"]["url"],
        "WINDOWS_SIZE": f"{release['windows']['bytes'] / 1_000_000:.1f} MB",
        "MACOS_SIZE": f"{release['macos']['bytes'] / 1_000_000:.1f} MB",
    }
    html = (SOURCE / "index.html").read_text(encoding="utf-8")
    for key, value in values.items():
        html = html.replace(f"@@{key}@@", escape(value, quote=True))
    reference_count = validate_site(html)

    # Only this exact build directory may be replaced; refuse symlinks or paths
    # outside the repository before any recursive deletion, including on Windows.
    expected = ROOT.resolve() / "_site"
    if OUTPUT.is_symlink() or OUTPUT.resolve() != expected or not expected.is_relative_to(ROOT.resolve()):
        raise ValueError("Unsafe build directory")
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    shutil.copytree(SOURCE, OUTPUT, ignore=shutil.ignore_patterns("package.json"))
    (OUTPUT / "index.html").write_text(html, encoding="utf-8")
    (OUTPUT / "release.json").write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUTPUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n", encoding="utf-8")
    (OUTPUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'  <url><loc>{SITE_URL}</loc></url>\n</urlset>\n', encoding="utf-8",
    )
    print(f"Built {OUTPUT.name}: {reference_count} references checked; release {release['tag']}.")


if __name__ == "__main__":
    main()
