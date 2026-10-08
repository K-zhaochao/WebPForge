"""用真实图片验证输出保护、编码结果、并发调度和 CLI 行为。"""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from PIL import Image

import webp_converter as wc


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="webpforge_test_")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.out = self.root / "输出"

    def picture(self, name="原图.png", mode="RGB", color="red", size=(40, 30)):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with Image.new(mode, size, color) as im:
            im.save(path)
        return path

    def convert(self, src, **kwargs):
        return wc.convert_one(wc.Item(src), wc.Options(**kwargs), self.out)

    def assert_valid(self, item, fmt="WEBP"):
        self.assertEqual(item.status, "完成", item.message)
        with Image.open(item.dst) as im:
            im.load()
            self.assertEqual(im.format, fmt)

    def test_default_keeps_existing_outputs(self):
        src = self.picture()
        first = self.convert(src)
        content = Path(first.dst).read_bytes()
        second = self.convert(src)
        self.assert_valid(second)
        self.assertNotEqual(first.dst, second.dst)
        self.assertEqual(Path(first.dst).read_bytes(), content)

    def test_overwrite_replaces_existing_output(self):
        src = self.picture()
        self.out.mkdir()
        target = self.out / "原图.webp"
        target.write_bytes(b"old output")
        result = self.convert(src, overwrite=True)
        self.assert_valid(result)
        self.assertEqual(Path(result.dst), target)
        self.assertEqual(len(list(self.out.iterdir())), 1)

    def test_overwrite_never_replaces_any_batch_source(self):
        png = self.picture("同名.png")
        webp = self.picture("同名.webp", color="blue")
        originals = {p: p.read_bytes() for p in (png, webp)}
        items = wc.collect_files([self.root])
        result = wc.run_batch(items, wc.Options(overwrite=True, workers=2), None)
        self.assertEqual((result.ok, result.failed), (2, 0))
        self.assertEqual(len({it.dst for it in items}), 2)
        for path, content in originals.items():
            self.assertEqual(path.read_bytes(), content)
        for item in items:
            self.assert_valid(item)

    def test_overwrite_keeps_all_colliding_batch_outputs(self):
        sources = [self.picture(f"目录{i}/same.png", color=(i * 40, 50, 70)) for i in range(6)]
        self.out.mkdir()
        (self.out / "same.webp").write_bytes(b"previous output")
        items = wc.collect_files(sources)
        result = wc.run_batch(items, wc.Options(overwrite=True, workers=6), self.out)
        self.assertEqual((result.ok, result.failed), (6, 0))
        self.assertEqual(len({it.dst for it in items}), 6)
        self.assertEqual(len(list(self.out.glob("*.webp"))), 6)

    def test_external_name_race_does_not_clobber_file(self):
        src = self.picture()
        publish = wc._publish_without_overwrite
        created = []

        def race(tmp, dst):
            if not created:
                dst.write_bytes(b"created by another process")
                created.append(dst)
            publish(tmp, dst)

        with patch.object(wc, "_publish_without_overwrite", side_effect=race):
            result = self.convert(src)
        self.assert_valid(result)
        self.assertEqual(created[0].read_bytes(), b"created by another process")
        self.assertNotEqual(Path(result.dst), created[0])

    def test_filename_reservations_are_released_after_batch(self):
        src = self.picture()
        item = wc.Item(src)
        wc.run_batch([item], wc.Options(), self.out)
        first = Path(item.dst)
        first.unlink()
        wc.run_batch([item], wc.Options(), self.out)
        self.assertEqual(Path(item.dst), first)

    def test_directory_failure_does_not_abort_other_items(self):
        bad = self.picture("blocked/bad.png")
        good = self.picture("good.png")
        self.out.mkdir()
        (self.out / "blocked").write_text("not a directory", encoding="utf-8")
        items = [wc.Item(bad, rel="blocked"), wc.Item(good)]
        seen = []
        result = wc.run_batch(items, wc.Options(keep_structure=True), self.out,
                              progress=lambda done, total, item: seen.append(done))
        self.assertEqual((result.ok, result.failed), (1, 1))
        self.assertEqual(seen, [1, 2])
        self.assert_valid(items[1])
        self.assertFalse(list(self.out.rglob(".wc_tmp_*")))

    def test_retry_failure_clears_previous_result(self):
        src = self.picture()
        item = self.convert(src)
        previous_output = Path(item.dst)
        src.write_bytes(b"corrupt")
        wc.convert_one(item, wc.Options(), self.out)
        self.assertEqual(item.status, "失败")
        self.assertEqual((item.dst, item.dst_size), ("", 0))
        self.assertTrue(previous_output.exists())
        self.assertFalse(list(self.out.glob(".wc_tmp_*")))

    def test_failed_save_preserves_existing_output_and_cleans_temp(self):
        src = self.picture()
        item = self.convert(src)
        target = Path(item.dst)
        content = target.read_bytes()

        def fail(image, path, **kwargs):
            Path(path).write_bytes(b"partial")
            raise OSError("disk full")

        with patch.object(Image.Image, "save", fail):
            result = self.convert(src, overwrite=True)
        self.assertEqual(result.status, "失败")
        self.assertEqual(target.read_bytes(), content)
        self.assertEqual(list(self.out.iterdir()), [target])

    def test_smaller_only_skip_has_no_stale_output(self):
        src = self.picture(size=(1, 1))
        item = wc.Item(src, dst="previous.webp", dst_size=999)
        opts = wc.Options(out_fmt="png", out_ext=".png", lossless=True, also_smaller_only=True)
        wc.convert_one(item, opts, self.out)
        self.assertEqual(item.status, "跳过")
        self.assertEqual(item.dst, "")
        self.assertEqual(item.dst_size, src.stat().st_size)
        self.assertEqual(list(self.out.iterdir()), [])

    def test_explicit_dot_output_means_working_directory(self):
        src = self.picture("source/image.png")
        self.out.mkdir()
        previous = Path.cwd()
        try:
            os.chdir(self.out)
            result = wc.convert_one(wc.Item(src), wc.Options(), Path("."))
        finally:
            os.chdir(previous)
        self.assertEqual(result.status, "完成", result.message)
        self.assertTrue((self.out / "image.webp").exists())
        self.assertFalse((src.parent / "image.webp").exists())

    def test_keep_structure_rejects_parent_traversal(self):
        src = self.picture()
        item = wc.Item(src, rel="../outside")
        wc.convert_one(item, wc.Options(keep_structure=True), self.out)
        self.assertEqual(item.status, "失败")
        self.assertFalse((self.root / "outside").exists())

    def test_scanning_excludes_nested_output_and_preserves_relative_paths(self):
        src = self.picture("相册/子目录/photo.png")
        generated = self.picture("相册/output/old.webp")
        album = self.root / "相册"
        items = wc.collect_files([album], exclude_dirs=[generated.parent])
        self.assertEqual([item.src for item in items], [src])
        self.assertEqual(items[0].rel, "子目录")
        self.assertEqual(wc.collect_files([album], recursive=False), [])
        # 显式把输出目录作为输入时，仍尊重用户选择。
        self.assertEqual(len(wc.collect_files([generated.parent], exclude_dirs=[generated.parent])), 1)

    def test_scanning_can_be_cancelled_without_touching_files(self):
        self.picture()
        self.assertEqual(wc.collect_files([self.root], should_stop=lambda: True), [])

    def test_preview_respects_exif_and_bounds(self):
        src = self.root / "rotated.jpg"
        with Image.new("RGB", (400, 200), "green") as im:
            exif = im.getexif()
            exif[0x0112] = 6
            im.save(src, exif=exif)
        thumbnail, size = wc.load_preview(src, bounds=(100, 100))
        try:
            self.assertEqual(size, (200, 400))
            self.assertEqual(thumbnail.size, (50, 100))
        finally:
            thumbnail.close()

    def test_lossless_png_keeps_every_pixel(self):
        src = self.root / "gradient.png"
        with Image.new("RGB", (64, 64)) as im:
            im.putdata([(x * 4, y * 4, (x * 13 + y * 17) % 256) for y in range(64) for x in range(64)])
            original = im.tobytes()
            im.save(src)
        result = self.convert(src, out_fmt="png", out_ext=".png", quality=30, lossless=True)
        self.assert_valid(result, "PNG")
        with Image.open(result.dst) as im:
            self.assertEqual(im.convert("RGB").tobytes(), original)

    def test_lossless_webp_preserves_alpha_and_hidden_rgb(self):
        src = self.picture(mode="RGBA", color=(20, 40, 90, 0))
        result = self.convert(src, lossless=True)
        self.assert_valid(result)
        with Image.open(result.dst) as im:
            self.assertEqual(im.convert("RGBA").getpixel((0, 0)), (20, 40, 90, 0))

    def test_palette_transparency_uses_jpeg_background(self):
        src = self.root / "palette.png"
        with Image.new("P", (20, 20), 0) as im:
            im.putpalette([255, 0, 0] + [0, 0, 0] * 255)
            im.save(src, transparency=0)
        result = self.convert(src, out_fmt="jpeg", out_ext=".jpg", bg="#145078", quality=100)
        self.assert_valid(result, "JPEG")
        with Image.open(result.dst) as im:
            for value, expected in zip(im.getpixel((0, 0)), (20, 80, 120)):
                self.assertLessEqual(abs(value - expected), 2)

    def test_rgba_png_quantization_is_supported(self):
        src = self.picture(mode="RGBA", color=(20, 80, 120, 120))
        result = self.convert(src, out_fmt="png", out_ext=".png", quality=50)
        self.assert_valid(result, "PNG")
        with Image.open(result.dst) as im:
            self.assertEqual(im.mode, "P")
            self.assertEqual(im.convert("RGBA").getpixel((0, 0))[3], 120)

    def test_exif_rotation_and_resize_are_applied_once(self):
        src = self.root / "rotated.jpg"
        with Image.new("RGB", (80, 40), "green") as im:
            exif = im.getexif()
            exif[0x0112] = 6
            exif[0x010E] = "test description"
            im.save(src, exif=exif)
        result = self.convert(src, max_edge=40)
        self.assert_valid(result)
        with Image.open(result.dst) as im:
            self.assertEqual(im.size, (20, 40))
            self.assertNotEqual(im.getexif().get(0x0112), 6)
            self.assertEqual(im.getexif().get(0x010E), "test description")

    def test_animation_keeps_short_durations_and_loop(self):
        for loop in (None, 0, 2):
            with self.subTest(loop=loop):
                src = self.root / f"animation-{loop}.gif"
                frames = [Image.new("RGB", (30, 20), color) for color in ("red", "green", "blue")]
                try:
                    frames[0].save(src, save_all=True, append_images=frames[1:],
                                   duration=[10, 30, 70], **({"loop": loop} if loop is not None else {}))
                finally:
                    for frame in frames:
                        frame.close()
                result = self.convert(src, lossless=True, max_edge=15)
                self.assert_valid(result)
                with Image.open(result.dst) as im:
                    self.assertEqual(im.n_frames, 3)
                    self.assertEqual(im.size, (15, 10))
                    self.assertEqual(im.info["loop"], 1 if loop is None else loop)
                    durations = []
                    for index in range(im.n_frames):
                        im.seek(index)
                        im.load()
                        durations.append(im.info["duration"])
                    self.assertEqual(durations, [10, 30, 70])

    def test_cancellation_before_publish_leaves_no_partial_file(self):
        src = self.picture()
        stopped = threading.Event()
        save = Image.Image.save

        def save_then_stop(image, *args, **kwargs):
            save(image, *args, **kwargs)
            stopped.set()

        with patch.object(Image.Image, "save", save_then_stop):
            item = wc.convert_one(wc.Item(src), wc.Options(), self.out, should_stop=stopped.is_set)
        self.assertEqual((item.status, item.dst, item.dst_size), ("已取消", "", 0))
        self.assertEqual(list(self.out.iterdir()), [])

    def test_completed_progress_is_not_blocked_by_first_slow_file(self):
        release = threading.Event()
        order = []
        items = [wc.Item(self.root / "slow.png"), wc.Item(self.root / "fast.png")]

        def convert(item, *args, **kwargs):
            if item.src.name == "slow.png":
                release.wait(3)
            item.status = "完成"
            return item

        def progress(done, total, item):
            order.append(item.src.name)
            if item.src.name == "fast.png":
                release.set()

        with patch.object(wc, "convert_one", side_effect=convert):
            result = wc.run_batch(items, wc.Options(workers=2), self.out, progress=progress)
        self.assertEqual(result.ok, 2)
        self.assertEqual(order, ["fast.png", "slow.png"])

    def test_stop_does_not_submit_remaining_tasks_or_count_them_as_skipped(self):
        items = [wc.Item(self.picture(f"{i}.png"), dst="stale", dst_size=999) for i in range(6)]
        stopped = threading.Event()
        seen = []

        def progress(done, total, item):
            seen.append(done)
            stopped.set()

        result = wc.run_batch(items, wc.Options(workers=1), self.out,
                              progress=progress, should_stop=stopped.is_set)
        self.assertEqual((result.ok, result.skipped, result.failed, result.cancelled), (1, 0, 0, 5))
        self.assertEqual(seen, list(range(1, 7)))
        self.assertEqual(len(list(self.out.glob("*.webp"))), 1)
        self.assertEqual(result.src_bytes, items[0].src_size)
        for item in items[1:]:
            self.assertEqual((item.status, item.dst, item.dst_size), ("已取消", "", 0))
        resumed = wc.run_batch(items[1:], wc.Options(), self.out)
        self.assertEqual((resumed.ok, resumed.cancelled), (5, 0))

    def test_unexpected_worker_exception_is_isolated(self):
        items = [wc.Item(self.root / "bad.png"), wc.Item(self.root / "good.png")]

        def convert(item, *args, **kwargs):
            if item.src.name == "bad.png":
                raise RuntimeError("unexpected worker error")
            item.status = "完成"
            return item

        with patch.object(wc, "convert_one", side_effect=convert):
            result = wc.run_batch(items, wc.Options(workers=2), self.out)
        self.assertEqual((result.ok, result.failed), (1, 1))
        self.assertIn("unexpected worker error", result.errors[0][1])

    def test_invalid_cli_options_do_not_create_outputs(self):
        src = self.picture()
        for flags in (["-q", "101"], ["--max-edge", "-1"], ["-j", "-1"],
                      ["--bg", "bad color"], ["-f", "jpeg", "--lossless"],
                      ["-f", "avif", "--lossless"]):
            with self.subTest(flags=flags), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    wc.run_cli(["-i", str(src), "-o", str(self.out)] + flags)
                self.assertEqual(caught.exception.code, 2)
        self.assertFalse(self.out.exists())

    def test_json_reports_each_output_and_failed_input(self):
        good = self.picture()
        bad = self.root / "broken.png"
        bad.write_bytes(b"broken")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            rc = wc.run_cli(["-i", str(good), str(bad), "-o", str(self.out), "--json"])
        result = json.loads(output.getvalue())
        self.assertEqual(rc, 3)
        self.assertEqual((result["ok"], result["failed"], result["cancelled"]), (1, 1, 0))
        self.assertEqual(result["items"][0]["status"], "ok")
        self.assertTrue(Path(result["items"][0]["output"]).is_file())
        self.assertIsNone(result["items"][1]["output"])

    def test_unknown_cli_argument_does_not_launch_gui(self):
        with patch.object(wc, "launch_gui") as gui, contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                wc.main(["--unknown-argument"])
            self.assertEqual(caught.exception.code, 2)
            gui.assert_not_called()

    def test_selftest_honors_report_path_from_main_arguments(self):
        report = self.root / "自检.txt"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(wc.main(["--selftest", str(report)]), 0)
        self.assertIn("全部通过", report.read_text(encoding="utf-8"))

    @unittest.skipUnless(os.name == "nt", "Windows console encoding")
    def test_cli_reconfigures_existing_gbk_streams_as_utf8(self):
        data = io.BytesIO()
        stream = io.TextIOWrapper(data, encoding="gbk")
        try:
            with patch.object(wc.sys, "stdout", stream), patch.object(wc.sys, "stderr", stream):
                wc.restore_cli_streams()
                print("中文 🖼 ✓", flush=True)
            self.assertEqual(data.getvalue().decode("utf-8").strip(), "中文 🖼 ✓")
        finally:
            stream.close()


if __name__ == "__main__":
    unittest.main()
