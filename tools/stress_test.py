#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""并发安全压力测试: 大量同名不同后缀的源文件必须各自得到唯一输出, 零失败。"""
import sys, shutil, random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import webp_converter as wc  # noqa: E402

root = Path(sys.argv[1] if len(sys.argv) > 1 else "_stress")
if root.exists():
    shutil.rmtree(root)
root.mkdir(parents=True)

random.seed(11)
# 构造极端冲突场景: 同一个 stem, 多种扩展名 -> 全部映射到同一个 .webp 目标名
stems = [f"same_name_{i}" for i in range(12)]
exts = [".png", ".jpg", ".bmp", ".tif", ".gif", ".webp"]
n = 0
for s in stems:
    for e in exts:
        im = Image.new("RGB", (60 + n % 40, 50 + n % 30), (n * 7 % 256, n * 13 % 256, n * 29 % 256))
        im.save(root / f"{s}{e}")
        n += 1
print(f"构造了 {n} 个高度冲突的源文件 (全部映射到 {len(stems)} 个目标名)")

items = wc.collect_files([root], recursive=True)
# 只取真实图片
items = [i for i in items if i.src.exists()]
print(f"扫描到 {len(items)} 个文件")

opts = wc.Options(quality=80, out_fmt="webp", out_ext=".webp", overwrite=False, workers=8)
res = wc.run_batch(items, opts, root)

print(f"\n成功={res.ok} 跳过={res.skipped} 失败={res.failed} 耗时={res.elapsed:.2f}s")
for p, m in res.errors[:10]:
    print("  !", Path(p).name, m)

out = sorted(root.glob("*.webp"))
n_webp_sources = sum(1 for i in items if i.src.suffix.lower() == ".webp")
n_produced = len(out) - n_webp_sources   # 源文件里已有的 .webp 会留在原地, 不算新产物
names = [p.name for p in out]
dupes = {x for x in names if names.count(x) > 1}
print(f"新产生的 .webp: {n_produced}  (输入 {len(items)} 个文件, 其中 {n_webp_sources} 个本身是 .webp)")
print("重名冲突:", dupes if dupes else "无")

# 每个 stem 的编号必须是连续无缺口的 0..N
from collections import defaultdict
byname = defaultdict(list)
for p in out:
    stem = p.stem.split("(")[0]
    byname[stem].append(p.stem)
gaps = []
for stem, lst in sorted(byname.items()):
    expect = {stem} | {f"{stem}({i})" for i in range(1, len(lst))}
    if set(lst) != expect:
        gaps.append((stem, sorted(set(lst) ^ expect)))
print("编号缺口:", gaps if gaps else "无")

# 每个输出都必须是可读的有效 webp
bad = []
for p in out:
    try:
        im = Image.open(p); im.load()
    except Exception as e:
        bad.append((p.name, str(e)))
print(f"损坏输出: {len(bad)}")
for b in bad[:5]:
    print("  !", b)

# 断言: 每个输入恰好产生一个新输出, 无重名, 无缺口, 无损坏
ok = True
if res.failed:
    print(">>> 失败: 存在转换失败"); ok = False
if dupes:
    print(">>> 失败: 输出文件重名"); ok = False
if bad:
    print(">>> 失败: 存在损坏输出"); ok = False
if gaps:
    print(">>> 失败: 输出编号存在缺口(说明有文件被覆盖)"); ok = False
if n_produced != len(items):
    print(f">>> 失败: 新输出数 {n_produced} != 输入数 {len(items)}"); ok = False

print("\n" + ("=== 并发压力测试: 全部通过 ===" if ok else "=== 并发压力测试: 存在失败 ==="))
sys.exit(0 if ok else 1)
