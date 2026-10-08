"""Package the rendered website and publish SHA-256 checksums for all assets."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

from build_site import ROOT, REPOSITORY, release_from_directory


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("tag")
    args = parser.parse_args()
    subprocess.run([sys.executable, str(ROOT / "tools/build_site.py"),
                    "--release-dir", str(args.directory), "--release-tag", args.tag], check=True)
    target = args.directory / f"WebPForge-{args.tag[1:]}-Web.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((ROOT / "_site").rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(ROOT / "_site"))
        archive.writestr("START-HERE.txt", "WebPForge web edition\nOfficial: https://webp.royi.net/\n"
                         "Do not open index.html using file://. Serve this folder over HTTP:\n"
                         "python -m http.server 4173 --bind 127.0.0.1\n"
                         "Open http://127.0.0.1:4173/ (no image uploads).\n"
                         "PWA installation requires HTTPS or localhost.\n")
    release = release_from_directory(args.directory, args.tag)
    release["web"] = {"url": f"https://github.com/{REPOSITORY}/releases/download/{args.tag}/{target.name}",
                      "bytes": target.stat().st_size}
    (args.directory / "release-manifest.json").write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
    assets = sorted(args.directory.glob("*.zip")) + [args.directory / "release-manifest.json"]
    checksums = "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n" for path in assets)
    (args.directory / "SHA256SUMS.txt").write_text(checksums, encoding="utf-8")
    print(checksums, end="")


if __name__ == "__main__":
    main()
