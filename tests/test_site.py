"""Dependency-free tests for deployment, offline cache versioning and packaging."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


class SiteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        shutil.copytree(ROOT / "site", self.root / "site")
        shutil.copytree(ROOT / "tools", self.root / "tools", ignore=shutil.ignore_patterns("__pycache__"))

    def tearDown(self):
        self.temp.cleanup()

    def run_tool(self, name, *arguments):
        result = subprocess.run([sys.executable, str(self.root / "tools" / name), *arguments],
                                cwd=self.root, capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_custom_domain_manifest_and_complete_public_precache(self):
        self.run_tool("build_site.py")
        output = self.root / "_site"
        html = (output / "index.html").read_text(encoding="utf-8")
        self.assertIn('rel="canonical" href="https://webp.royi.net/"', html)
        self.assertEqual((output / "CNAME").read_text().strip(), "webp.royi.net")
        self.assertIn("https://webp.royi.net/sitemap.xml", (output / "robots.txt").read_text())
        manifest = json.loads((output / "manifest.webmanifest").read_text(encoding="utf-8"))
        self.assertEqual(manifest["display"], "standalone")
        for icon in manifest["icons"]:
            self.assertTrue((output / icon["src"]).is_file())
        worker = (output / "sw.js").read_text(encoding="utf-8")
        self.assertNotIn("@@", worker)
        urls = json.loads(re.search(r"const PRECACHE = (.*);", worker).group(1))
        self.assertTrue(any(re.fullmatch(r"\./pwa\.[a-f0-9]{16}\.js", url) for url in urls))
        for module in ("preferences", "interface", "messages"):
            self.assertTrue(any(re.fullmatch(r"\./" + module + r"\.[a-f0-9]{16}\.js", url) for url in urls))
        self.assertTrue(any(re.fullmatch(r"\./assets/heading-sc\.[a-f0-9]{16}\.woff2", url) for url in urls))
        worker_url = re.search(r'name="webpforge-worker" content="(.*?)"', html).group(1)
        self.assertTrue((output / worker_url).is_file())
        self.assertNotEqual(worker_url, "./sw.js")
        app_path = re.search(r'src="(app\.[a-f0-9]{16}\.js)"', html).group(1)
        self.assertRegex((output / app_path).read_text(encoding="utf-8"), r'pwa\.[a-f0-9]{16}\.js')
        for url in urls:
            self.assertTrue((output / url).exists())
        self.assertTrue(all(url.startswith("./") for url in urls))

    def test_cache_version_is_reproducible_and_changes_with_content(self):
        self.run_tool("build_site.py")
        old = (self.root / "_site/sw.js").read_bytes()
        self.run_tool("build_site.py")
        self.assertEqual(old, (self.root / "_site/sw.js").read_bytes())
        with (self.root / "site/styles.css").open("a", encoding="utf-8") as file:
            file.write("\n/* content update */\n")
        self.run_tool("build_site.py")
        self.assertNotEqual(old, (self.root / "_site/sw.js").read_bytes())

    def test_web_archive_matches_release_assets_and_checksums(self):
        directory = self.root / "out"
        directory.mkdir()
        for suffix in ("Windows-x64", "macOS-ARM64", "macOS-Intel"):
            (directory / f"WebPForge-1.1.0-{suffix}.zip").write_bytes(b"test-package")
        self.run_tool("package_web.py", str(directory), "v1.1.0")
        with zipfile.ZipFile(directory / "WebPForge-1.1.0-Web.zip") as archive:
            self.assertIn("START-HERE.txt", archive.namelist())
            self.assertIn("manifest.webmanifest", archive.namelist())
            self.assertIn(b"releases/download/v1.1.0/", archive.read("index.html"))
        release = json.loads((directory / "release-manifest.json").read_text())
        self.assertEqual(release["tag"], "v1.1.0")
        self.assertEqual(release["intel"]["bytes"], len(b"test-package"))
        for line in (directory / "SHA256SUMS.txt").read_text().splitlines():
            expected, name = line.split("  ", 1)
            self.assertEqual(hashlib.sha256((directory / name).read_bytes()).hexdigest(), expected)

    def test_missing_package_stops_release_before_publication(self):
        directory = self.root / "out"
        directory.mkdir()
        result = subprocess.run([sys.executable, str(self.root / "tools/package_web.py"), str(directory), "v1.1.0"], capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((directory / "SHA256SUMS.txt").exists())


if __name__ == "__main__":
    unittest.main()
