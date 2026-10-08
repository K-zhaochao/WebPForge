"""Build the dependency-free GitHub Pages site and validate its local references.

    python tools/build_site.py
    python -m http.server 4173 --bind 127.0.0.1 --directory _site

Use --refresh-release during deployment to resolve the latest complete public
release. Local builds use the checked-in release.json and need no network.
"""

import argparse
import hashlib
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
SITE_URL = "https://webp.royi.net/"
REPOSITORY = "K-zhaochao/WebPForge"


def is_within(path, parent):
    """Path containment compatible with the desktop's Python 3.8 test matrix."""
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


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
    for platform, suffix in (("intel", "-macOS-Intel.zip"), ("web", "-Web.zip")):
        matches = [asset for asset in assets if asset["name"].endswith(suffix)]
        if len(matches) == 1:
            asset = matches[0]
            result[platform] = {"url": asset["browser_download_url"], "bytes": asset["size"]}
    return result


def validate_release(release):
    prefix = f"https://github.com/{REPOSITORY}/releases/"
    if not release["url"].startswith(prefix + "tag/"):
        raise ValueError("Unexpected release URL")
    for platform in ("windows", "macos", *(key for key in ("intel", "web") if key in release)):
        if not release[platform]["url"].startswith(prefix + "download/"):
            raise ValueError(f"Unexpected {platform} asset URL")
        if not isinstance(release[platform]["bytes"], int) or release[platform]["bytes"] <= 0:
            raise ValueError(f"Invalid {platform} asset size")


def release_from_directory(directory, tag):
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag or ""):
        raise ValueError("A stable vX.Y.Z release tag is required")
    release = {"tag": tag, "url": f"https://github.com/{REPOSITORY}/releases/tag/{tag}"}
    for platform, suffix in (("windows", "Windows-x64"), ("macos", "macOS-ARM64"), ("intel", "macOS-Intel")):
        asset = Path(directory) / f"WebPForge-{tag[1:]}-{suffix}.zip"
        release[platform] = {"url": f"https://github.com/{REPOSITORY}/releases/download/{tag}/{asset.name}",
                             "bytes": asset.stat().st_size}
    return release


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
        if not is_within(target, SOURCE.resolve()) or not target.is_file():
            references.errors.append(f"Missing or unsafe local reference: {reference}")
    for sample in json.loads((SOURCE / "assets" / "samples.json").read_text(encoding="utf-8")):
        for field, size_field in (("source", "sourceBytes"), ("preview", "outputBytes")):
            target = (SOURCE / sample[field]).resolve()
            if not is_within(target, SOURCE.resolve()) or not target.is_file():
                references.errors.append(f"Missing or unsafe sample: {sample[field]}")
            elif target.stat().st_size != sample[size_field]:
                references.errors.append(f"Sample size has drifted: {sample[field]}")
        thumbnail = (SOURCE / sample["thumbnail"]).resolve()
        if not is_within(thumbnail, SOURCE.resolve()) or not thumbnail.is_file():
            references.errors.append(f"Missing sample thumbnail: {sample['thumbnail']}")
    if "@@" in html:
        references.errors.append("Unresolved template tokens")
    if references.errors:
        raise ValueError("\n".join(references.errors))
    return len(references.references)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-release", action="store_true")
    parser.add_argument("--release-dir", help="Build from locally packaged release assets")
    parser.add_argument("--release-tag")
    args = parser.parse_args()
    if args.refresh_release and args.release_dir:
        parser.error("Choose one release source")
    release = (release_from_directory(args.release_dir, args.release_tag) if args.release_dir
               else refresh_release() if args.refresh_release
               else json.loads((SOURCE / "release.json").read_text(encoding="utf-8")))
    validate_release(release)
    fingerprint = hashlib.sha256(json.dumps(release, sort_keys=True).encode())
    for path in sorted(SOURCE.rglob("*")):
        if path.is_file():
            fingerprint.update(path.relative_to(SOURCE).as_posix().encode())
            fingerprint.update(path.read_bytes())
    build_id = fingerprint.hexdigest()[:16]
    worker_filename = f"sw.{build_id}.js"
    values = {
        "SITE_URL": SITE_URL,
        "WORKER_URL": "./" + worker_filename,
        "RELEASE_TAG": release["tag"],
        "RELEASE_URL": release["url"],
        "WINDOWS_URL": release["windows"]["url"],
        "MACOS_URL": release["macos"]["url"],
        "WINDOWS_SIZE": f"{release['windows']['bytes'] / 1_000_000:.1f} MB",
        "MACOS_SIZE": f"{release['macos']['bytes'] / 1_000_000:.1f} MB",
        "INTEL_URL": release.get("intel", {}).get("url", release["url"]),
        "INTEL_LABEL": "下载 Intel 版" if "intel" in release else "查看 Intel 版本",
        "WEB_URL": release.get("web", {}).get("url", release["url"]),
    }
    html = (SOURCE / "index.html").read_text(encoding="utf-8")
    for key, value in values.items():
        html = html.replace(f"@@{key}@@", escape(value, quote=True))
    reference_count = validate_site(html)

    # Only this exact build directory may be replaced; refuse symlinks or paths
    # outside the repository before any recursive deletion, including on Windows.
    expected = ROOT.resolve() / "_site"
    if OUTPUT.is_symlink() or OUTPUT.resolve() != expected or not is_within(expected, ROOT.resolve()):
        raise ValueError("Unsafe build directory")
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    shutil.copytree(SOURCE, OUTPUT, ignore=shutil.ignore_patterns("package.json"))
    # Pages/custom-domain CDNs may cache JS for hours. Content-addressed URLs
    # keep each HTML/module/font set together and bypass stale edge objects.
    versioned = {path.name: f"{path.stem}.{build_id}{path.suffix}" for path in OUTPUT.rglob("*")
                 if path.is_file() and path.suffix in (".js", ".css", ".woff2") and path.name != "sw.js"}
    def rewrite_references(text):
        for before, after in versioned.items():
            text = text.replace(before, after)
        return text
    for path in list(OUTPUT.rglob("*")):
        if path.is_file() and path.name in versioned:
            if path.suffix in (".js", ".css"):
                path.write_text(rewrite_references(path.read_text(encoding="utf-8")), encoding="utf-8")
            path.rename(path.with_name(versioned[path.name]))
    html = rewrite_references(html)
    (OUTPUT / "index.html").write_text(html, encoding="utf-8")
    (OUTPUT / "release.json").write_text(json.dumps(release, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUTPUT / "CNAME").write_text(urllib.parse.urlsplit(SITE_URL).hostname + "\n", encoding="utf-8")
    (OUTPUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}sitemap.xml\n", encoding="utf-8")
    (OUTPUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'  <url><loc>{SITE_URL}</loc></url>\n</urlset>\n', encoding="utf-8",
    )
    manifest = json.loads((OUTPUT / "manifest.webmanifest").read_text(encoding="utf-8"))
    for icon in manifest["icons"]:
        if not (OUTPUT / icon["src"]).is_file():
            raise ValueError(f"Missing PWA icon: {icon['src']}")
    # Hash the complete rendered application, including release URLs and fonts.
    # A deployment changes the cache version even if the software tag is unchanged.
    files = sorted(path for path in OUTPUT.rglob("*") if path.is_file() and path.name != "sw.js")
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(OUTPUT).as_posix().encode())
        digest.update(path.read_bytes())
    urls = ["./"] + ["./" + path.relative_to(OUTPUT).as_posix() for path in files
                       if path.suffix not in (".md", ".txt") and path.name != "CNAME"]
    worker = (OUTPUT / "sw.js").read_text(encoding="utf-8")
    worker = worker.replace("@@CACHE_VERSION@@", digest.hexdigest()[:16])
    worker = worker.replace("@@PRECACHE_URLS@@", json.dumps(urls, ensure_ascii=False))
    (OUTPUT / "sw.js").write_text(worker, encoding="utf-8")
    (OUTPUT / worker_filename).write_text(worker, encoding="utf-8")
    print(f"Built {OUTPUT.name}: {reference_count} references checked; release {release['tag']}.")


if __name__ == "__main__":
    main()
