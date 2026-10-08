#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""验证打包程序的自检、标准输出重定向和四种格式的真实转换。"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from PIL import Image


def main():
    executable = Path(sys.argv[1] if len(sys.argv) > 1 else "dist/WebPForge.exe").resolve()
    if not executable.is_file():
        raise FileNotFoundError(executable)

    def run(*args):
        return subprocess.run([str(executable), *map(str, args)], capture_output=True,
                              text=True, encoding="utf-8", timeout=45)

    with tempfile.TemporaryDirectory(prefix="webpforge_packaged_") as temp:
        root = Path(temp)
        source = root / "中文 图片.png"
        with Image.new("RGBA", (120, 90), (30, 120, 200, 128)) as image:
            image.save(source)
        original = source.read_bytes()
        report = root / "自检 报告.txt"
        check = run("--selftest", report)
        assert check.returncode == 0, check.stderr or check.stdout
        assert "全部通过" in report.read_text(encoding="utf-8")
        assert "Pillow" in check.stdout, "Packaged standard output is missing"
        print("[OK] packaged self-test, Unicode report path, stdout capture")

        for fmt in ("webp", "png", "jpeg", "avif"):
            result = run("--cli", "-i", source, "-o", root / fmt, "-f", fmt,
                         "--max-edge", "60", "--json")
            assert result.returncode == 0, result.stderr or result.stdout
            data = json.loads(result.stdout)
            assert (data["ok"], data["failed"], data["cancelled"]) == (1, 0, 0), data
            output = Path(data["items"][0]["output"])
            with Image.open(output) as image:
                image.load()
                assert image.format == fmt.upper(), image.format
                assert image.size == (60, 45), image.size
            assert source.read_bytes() == original, "Input file was modified"
            print(f"[OK] {fmt.upper()} conversion, resize, JSON, source protection")

        invalid = run("--cli", "-i", source, "-q", "101")
        assert invalid.returncode == 2, invalid
        assert "质量" in invalid.stderr, "Packaged stderr is missing"
        assert "--selftest" in run("--help").stdout
        print("[OK] CLI validation, stderr capture, help")
    return 0


if __name__ == "__main__":
    sys.exit(main())
