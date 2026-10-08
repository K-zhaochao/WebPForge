"""Regression tests for executable modes lost during macOS release assembly."""
from pathlib import Path
import plistlib
import struct
import tempfile
import unittest
import zipfile

from tools.verify_release import verify_mac, verify_windows


class ReleaseTests(unittest.TestCase):
    def mac_archive(self, directory, mode=0o100755, cpu=0x100000C, version="1.1.1"):
        path = Path(directory) / "mac.zip"
        with zipfile.ZipFile(path, "w") as package:
            entry = zipfile.ZipInfo("WebPForge.app/Contents/MacOS/WebPForge")
            entry.create_system = 3
            entry.external_attr = mode << 16
            package.writestr(entry, b"\xcf\xfa\xed\xfe" + struct.pack("<I", cpu) + b"\0" * 24)
            package.writestr("WebPForge.app/Contents/Info.plist", plistlib.dumps({
                "CFBundleShortVersionString": version, "CFBundleVersion": version}))
        return path

    def test_mac_architecture_and_executable_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            verify_mac(self.mac_archive(directory), "ARM64", "1.1.1")
            verify_mac(self.mac_archive(directory, cpu=0x1000007), "Intel", "1.1.1")

    def test_missing_execute_mode_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "executable permission"):
                verify_mac(self.mac_archive(directory, mode=0o100644), "ARM64", "1.1.1")

    def test_wrong_architecture_and_bundle_version_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "architecture"):
                verify_mac(self.mac_archive(directory, cpu=0x1000007), "ARM64", "1.1.1")
            with self.assertRaisesRegex(ValueError, "bundle version"):
                verify_mac(self.mac_archive(directory, version="1.0.0"), "ARM64", "1.1.1")

    def test_windows_x64_architecture(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "win.zip"
            binary = bytearray(128)
            binary[:2] = b"MZ"
            struct.pack_into("<I", binary, 60, 80)
            binary[80:84] = b"PE\0\0"
            struct.pack_into("<H", binary, 84, 0x8664)
            with zipfile.ZipFile(path, "w") as package:
                package.writestr("WebPForge.exe", binary)
            verify_windows(path)


if __name__ == "__main__":
    unittest.main()
