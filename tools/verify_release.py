"""Verify actual executable architecture, macOS mode/version and release hashes."""
import argparse
import hashlib
import json
from pathlib import Path
import plistlib
import struct
import zipfile


def verify_mac(archive, architecture, version):
    with zipfile.ZipFile(archive) as package:
        entry = package.getinfo("WebPForge.app/Contents/MacOS/WebPForge")
        binary = package.read(entry)
        if binary[:4] != b"\xcf\xfa\xed\xfe":
            raise ValueError("Expected a 64-bit little-endian Mach-O application")
        expected = {"ARM64": 0x100000C, "Intel": 0x1000007}[architecture]
        if struct.unpack("<I", binary[4:8])[0] != expected:
            raise ValueError(f"Incorrect {architecture} Mach-O architecture")
        if not (entry.external_attr >> 16) & 0o111:
            raise ValueError(f"{architecture} executable permission is missing")
        info = plistlib.loads(package.read("WebPForge.app/Contents/Info.plist"))
        if info["CFBundleShortVersionString"] != version or info["CFBundleVersion"] != version:
            raise ValueError("macOS bundle version does not match release")


def verify_windows(archive):
    with zipfile.ZipFile(archive) as package:
        binary = package.read("WebPForge.exe")
        if binary[:2] != b"MZ":
            raise ValueError("Missing Windows executable")
        offset = struct.unpack("<I", binary[60:64])[0]
        if binary[offset:offset + 4] != b"PE\0\0" or struct.unpack("<H", binary[offset + 4:offset + 6])[0] != 0x8664:
            raise ValueError("Expected a Windows x64 PE executable")


def verify_release(directory, tag):
    directory = Path(directory)
    version = tag.removeprefix("v") if hasattr(tag, "removeprefix") else tag[1:]
    for architecture in ("ARM64", "Intel"):
        verify_mac(directory / f"WebPForge-{version}-macOS-{architecture}.zip", architecture, version)
    verify_windows(directory / f"WebPForge-{version}-Windows-x64.zip")
    with zipfile.ZipFile(directory / f"WebPForge-{version}-Web.zip") as package:
        if "@@" in package.read("sw.js").decode() or "@@" in package.read("index.html").decode():
            raise ValueError("Unrendered web release")
    manifest = json.loads((directory / "release-manifest.json").read_text(encoding="utf-8"))
    if manifest["tag"] != tag:
        raise ValueError("Release manifest tag does not match")
    for line in (directory / "SHA256SUMS.txt").read_text().splitlines():
        digest, name = line.split("  ", 1)
        target = directory / name
        if target.parent.resolve() != directory.resolve():
            raise ValueError("Unexpected checksum path")
        if hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Checksum mismatch: {name}")
    print(f"Verified {tag}: Windows x64, Mac ARM64/Intel permissions and versions, Web rendering, SHA256.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("tag")
    args = parser.parse_args()
    verify_release(args.directory, args.tag)
