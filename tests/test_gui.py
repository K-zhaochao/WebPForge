"""在主线程启动真实窗口并操作真实控件，不复刻界面处理逻辑。"""
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from PIL import Image

import webp_converter as wc

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ImportError:
    tk = None


def widgets(parent):
    for child in parent.winfo_children():
        yield child
        yield from widgets(child)


@unittest.skipIf(tk is None or (sys.platform.startswith("linux") and not os.environ.get("DISPLAY")),
                 "GUI tests require tkinter and a display (Linux: xvfb-run)")
class GuiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="webpforge_gui_")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sources = []
        for index in range(3):
            src = self.root / f"图片{index}.png"
            with Image.new("RGB", (180, 120), (index * 80, 20, 160)) as im:
                im.save(src)
            self.sources.append(src)
        self.out = self.root / "out"
        self.drop = None

    def button(self, root, text):
        return next(w for w in widgets(root) if isinstance(w, ttk.Button) and text in w.cget("text"))

    def check(self, root, text):
        return next(w for w in widgets(root) if isinstance(w, ttk.Checkbutton) and text in w.cget("text"))

    def tree(self, root):
        return next(w for w in widgets(root) if isinstance(w, ttk.Treeview))

    def custom_output(self, root, path):
        radio = next(w for w in widgets(root) if isinstance(w, ttk.Radiobutton) and w.cget("value") == "custom")
        radio.invoke()
        entry = next(w for w in radio.master.winfo_children() if isinstance(w, ttk.Entry))
        entry.delete(0, "end")
        entry.insert(0, path)

    def run_gui(self, scenario):
        errors = []
        mainloop = tk.Tk.mainloop

        def enable_drop(root, callback):
            self.drop = callback
            return False

        def drive(root):
            root.update_idletasks()
            root.withdraw()
            original_destroy = root.destroy

            def destroy():
                for job in root.tk.call("after", "info"):
                    root.after_cancel(job)
                original_destroy()
            root.destroy = destroy

            def fail(exc):
                errors.append(exc)
                destroy()

            root.report_callback_exception = lambda kind, value, trace: fail(value.with_traceback(trace))
            steps = scenario(root)

            def advance():
                try:
                    condition = next(steps)
                except StopIteration:
                    root.tk.call(root.protocol("WM_DELETE_WINDOW"))
                    return
                except BaseException as exc:
                    fail(exc)
                    return
                deadline = time.monotonic() + 10

                def poll():
                    try:
                        if condition():
                            advance()
                        elif time.monotonic() > deadline:
                            fail(AssertionError("GUI operation timed out"))
                        else:
                            root.after(20, poll)
                    except BaseException as exc:
                        fail(exc)
                root.after(10, poll)

            root.after(0, advance)
            root.after(15000, lambda: fail(AssertionError("GUI did not close")))
            mainloop(root)

        with patch.object(tk.Tk, "mainloop", drive), \
                patch.object(wc, "enable_windows_drop", side_effect=enable_drop), \
                patch.object(filedialog, "askopenfilenames", return_value=tuple(map(str, self.sources))), \
                patch.object(messagebox, "showinfo"), \
                patch.object(messagebox, "showwarning") as warning, \
                patch.object(messagebox, "showerror") as error, \
                patch.object(messagebox, "askyesno", return_value=True):
            self.warning, self.error = warning, error
            self.assertEqual(wc.launch_gui(), 0)
        if errors:
            raise errors[0]

    def test_add_preview_convert_and_retry_only_failed(self):
        self.sources[1].write_bytes(b"broken image")

        def scenario(root):
            start = self.button(root, "开始转换")
            retry = self.button(root, "重试失败")
            self.button(root, "添加图片").invoke()
            yield lambda: not start.instate(["disabled"])
            tree = self.tree(root)
            self.assertEqual(len(tree.get_children()), 3)
            # 同一来源以另一种路径写法拖入，也不能重复添加。
            self.drop([str(p.parent / "." / p.name) for p in self.sources])
            yield lambda: not start.instate(["disabled"])
            self.assertEqual(len(tree.get_children()), 3)
            tree.selection_set("0")
            canvas = next(w for w in widgets(root) if isinstance(w, tk.Canvas))
            yield lambda: any(canvas.type(item) == "image" for item in canvas.find_all())
            image_item = next(item for item in canvas.find_all() if canvas.type(item) == "image")
            image_name = canvas.itemcget(image_item, "image")
            self.assertLessEqual(int(root.tk.call("image", "width", image_name)), canvas.winfo_width())
            self.assertLessEqual(int(root.tk.call("image", "height", image_name)), canvas.winfo_height())
            self.custom_output(root, str(self.out))
            self.check(root, "智能模式").invoke()
            start.invoke()
            yield lambda: not start.instate(["disabled"])
            self.assertEqual(len(list(self.out.glob("*.webp"))), 2)
            self.assertFalse(retry.instate(["disabled"]))
            self.warning.assert_called_once()
            with Image.new("RGB", (40, 30), "blue") as im:
                im.save(self.sources[1])
            retry.invoke()
            yield lambda: not start.instate(["disabled"])
            self.assertEqual(len(list(self.out.glob("*.webp"))), 3)
            self.assertTrue(retry.instate(["disabled"]))
            self.assertTrue(all("ok" in tree.item(item, "tags") for item in tree.get_children()))
            self.error.assert_not_called()
        self.run_gui(scenario)

    def test_busy_queue_is_locked_and_stop_can_resume(self):
        started, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        convert = wc.convert_one

        def wait_then_convert(*args, **kwargs):
            started.set()
            if not release.wait(5):
                raise RuntimeError("test did not release encoder")
            return convert(*args, **kwargs)

        def scenario(root):
            start = self.button(root, "开始转换")
            self.button(root, "添加图片").invoke()
            yield lambda: not start.instate(["disabled"])
            self.custom_output(root, str(self.out))
            self.check(root, "智能模式").invoke()
            start.invoke()
            yield started.is_set
            tree = self.tree(root)
            tree.selection_set("0")
            for text in ("添加图片", "添加文件夹", "移除选中", "清空列表"):
                button = self.button(root, text)
                self.assertTrue(button.instate(["disabled"]))
                button.invoke()
            self.drop([str(self.root / "unwanted.png")])
            self.assertEqual(len(tree.get_children()), 3)
            self.button(root, "停止").invoke()
            release.set()
            yield lambda: not start.instate(["disabled"])
            self.assertFalse(list(self.out.glob("*.webp")))
            self.assertTrue(all("已取消" in tree.item(row, "values")[2] for row in tree.get_children()))
            start.invoke()
            yield lambda: not start.instate(["disabled"])
            self.assertEqual(len(list(self.out.glob("*.webp"))), 3)
            self.error.assert_not_called()
        with patch.object(wc, "convert_one", side_effect=wait_then_convert):
            self.run_gui(scenario)

    def test_empty_output_and_invalid_size_are_reported_before_start(self):
        def scenario(root):
            start = self.button(root, "开始转换")
            self.button(root, "添加图片").invoke()
            yield lambda: not start.instate(["disabled"])
            self.custom_output(root, "")
            start.invoke()
            self.assertIn("选择输出文件夹", self.error.call_args[0][1])
            self.assertFalse(start.instate(["disabled"]))
            self.assertFalse(list(self.root.glob("*.webp")))
            self.custom_output(root, str(self.out))
            edge = next(w for w in widgets(root) if isinstance(w, ttk.Entry) and w.get() == "0")
            edge.delete(0, "end")
            edge.insert(0, "wrong")
            start.invoke()
            self.assertIn("最长边", self.error.call_args[0][1])
            self.assertFalse(self.out.exists())
            # 切换到不支持无损的格式时，界面清除并禁用无损开关。
            lossless = self.check(root, "无损模式")
            lossless.invoke()
            combo = next(w for w in widgets(root) if isinstance(w, ttk.Combobox))
            combo.set("JPEG (.jpg)")
            combo.event_generate("<<ComboboxSelected>>")
            self.assertTrue(lossless.instate(["disabled"]))
            self.assertFalse(root.getvar(lossless.cget("variable")))
        self.run_gui(scenario)

    def test_close_waits_for_running_encoder_to_clean_up(self):
        started, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        convert = wc.convert_one

        def delayed(*args, **kwargs):
            started.set()
            if not release.wait(5):
                raise RuntimeError("encoder was not released")
            return convert(*args, **kwargs)

        def scenario(root):
            start = self.button(root, "开始转换")
            self.button(root, "添加图片").invoke()
            yield lambda: not start.instate(["disabled"])
            self.custom_output(root, str(self.out))
            start.invoke()
            yield started.is_set
            root.tk.call(root.protocol("WM_DELETE_WINDOW"))
            self.assertTrue(root.winfo_exists())
            self.assertTrue(self.button(root, "停止").instate(["disabled"]))
            release.set()
            # 由应用在工作线程结束后自行关闭；超时由 harness 报告。
            yield lambda: False

        with patch.object(wc, "convert_one", side_effect=delayed):
            self.run_gui(scenario)
        self.assertFalse(list(self.out.glob("*.webp")))
        self.assertFalse(list(self.out.glob(".wc_tmp_*")))


if __name__ == "__main__":
    unittest.main()
