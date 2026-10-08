<div align="center">

# WebPForge

**批量图片转 WebP 的桌面工具 · 双击即用 · 无需安装 Python**

[![Build & Release](https://github.com/K-zhaochao/WebPForge/actions/workflows/build.yml/badge.svg)](https://github.com/K-zhaochao/WebPForge/actions/workflows/build.yml)
[![Release](https://img.shields.io/github/v/release/K-zhaochao/WebPForge?color=3ac0d6&label=release)](https://github.com/K-zhaochao/WebPForge/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-6f7cff)

**中文** · [English](README.en.md)

[**访问官网 · 直接在线转换 / 安装手机轻应用**](https://webp.royi.net/)

把一堆 JPG / PNG / BMP / GIF / TIFF 拖进去，点一下「开始转换」，就全部变成体积更小的 WebP。

</div>

---

## 下载

前往 [**Releases**](https://github.com/K-zhaochao/WebPForge/releases/latest) 下载对应系统的压缩包，解压后直接双击运行：

| 系统 | 文件 |
|---|---|
| Windows 10/11 (x64) | `WebPForge-<版本>-Windows-x64.zip` → 双击 `WebPForge.exe` |
| macOS（Apple Silicon / M 系列） | `WebPForge-<版本>-macOS-ARM64.zip` → 双击 `WebPForge.app` |
| macOS（Intel） | `WebPForge-<版本>-macOS-Intel.zip` → 双击 `WebPForge.app` |

> **Intel Mac 用户**：v1.1.0 起正式 Release 自动包含 Intel 包，与 Apple Silicon 分开下载。

> 程序未做代码签名，首次运行会有系统提示，属正常现象：
> - **Windows**：SmartScreen 提示 →「更多信息」→「仍要运行」
> - **macOS**：右键点击 App →「打开」→ 再点「打开」（或执行 `xattr -cr WebPForge.app`）

---

## 官网与在线体验

官网：[**webp.royi.net**](https://webp.royi.net/)

- 默认直接在线使用；按系统下载 Windows x64、macOS Apple Silicon / Intel 版。
- 官网支持中英文、浅色 / 暗色主题切换；记住选择，首次主题跟随系统。手机端同样可直接切换。
- 手机支持 PWA 轻应用（不是 APK / App Store 原生应用）。Android 用浏览器安装，iOS 用 Safari「分享 → 添加到主屏幕」，缓存完成后支持离线转换。
- 在线体验使用浏览器在本机实际编码 WebP，支持画质调整、原图对比、替换图片与下载结果。
- 不上传用户图片，不使用分析服务；样图和字体均由官网自身托管。
- 浏览器体验仅处理静态 JPG / PNG / WebP，单张最大 20 MB、1,600 万像素、单边 8,192 像素。批量、动画与无损转换请使用桌面版。

本地预览无需安装前端依赖：

```bash
python tools/build_site.py
python -m http.server 4173 --bind 127.0.0.1 --directory _site
```

访问 `http://127.0.0.1:4173/`。官网使用 GitHub Actions 自动部署到 GitHub Pages，
更新 `main` 中的官网文件或发布正式 Release 后会自动构建。
维护方式与验证记录见 [官网维护说明](docs/website.md)。

## 功能特点

| 能力 | 说明 |
|---|---|
| 批量转换 | 后台扫描文件夹，限制同时在途任务数，按实际完成顺序更新进度 |
| 拖拽添加 | Windows 下直接把文件/文件夹拖进窗口即可 |
| 保留画质 | 可调质量 1–100，也可开启**无损模式** |
| 保留透明 | PNG 的透明通道不会丢失 |
| 纠正方向 | 自动处理手机照片的 EXIF 旋转标记 |
| 保留动画 | 动图 GIF 转成**动态 WebP**，帧和循环都在 |
| 智能模式 | 结果不小于原图时跳过，不产生输出文件；界面默认开启，CLI 用 `--smaller-only` 开启 |
| 原图保护 | 默认重名自动改为 `名字(1).webp`；可覆盖已有输出，始终保护本批全部输入文件 |
| 停止与重试 | 停止后可继续未完成项，也可仅重试失败项；单个文件失败不影响整批 |
| 图片预览 | 按照片实际方向预览，自适应窗口尺寸，转换后显示真实输出大小 |
| 保留结构 | 可选择重建子文件夹层级 |
| 缩放限制 | 可指定「最长边不超过 N 像素」批量压尺寸 |
| 中文友好 | 中文文件名、中文路径完全支持 |
| 纯离线 | 不联网、不上传，图片只在本机处理 |

支持的输入格式：JPG / JPEG / PNG / BMP / GIF / TIFF / TGA / ICO / WebP / AVIF 及 Pillow 支持的其它格式。
输出格式：**WebP（默认）**，也支持 PNG / JPEG / AVIF。

AVIF 编码取决于当前 Pillow 的支持情况，建议使用较新的 Python 与 Pillow。
HEIC、RAW 等扩展名可能需要额外的 Pillow 插件；不支持或损坏的文件会单独报告失败。

---

## 界面说明

```
┌────────────────────────────────────────────────────────────┐
│  ➕添加图片 📁添加文件夹 ➖移除选中 🗑清空  ⭐关于  ■停止 ▶开始转换│
├──────────────────────────────┬─────────────────────────────┤
│  文件            原始大小  状态│  ┌─预览─┬─设置─┐            │
│  photo1.jpg      2.1 MB   完成│  │             │            │
│  照片2.png       840 KB   等待│  │   图片预览   │            │
│  ...                          │  │             │            │
├──────────────────────────────┴─────────────────────────────┤
│  ████████████████████░░░░░░░░  正在转换 128/200 …           │
│              共 200 张 · 已完成 128 · 省 76%   GitHub ⭐     │
└────────────────────────────────────────────────────────────┘
```

### 界面里的仓库入口

程序内置了三个通往开源仓库的入口，点一下就会用默认浏览器打开：

| 位置 | 说明 |
|---|---|
| 顶部工具条 **⭐ 关于 / 项目主页** | 弹出「关于」窗口，内含项目简介与打开按钮 |
| 设置标签页 → **关于** 分组 | 直接显示仓库地址，可点击，并提供「报告问题 / 建议」 |
| 底部状态栏右下角 **GitHub ⭐** | 一键跳转项目主页 |

快捷键 `Ctrl+U` 同样可以打开「关于」窗口。

### 停止、继续与重试

- 点击「停止」或按 `Esc` 后不再启动新任务，等待正在编码的图片结束并清理临时文件。
- 取消项单独标记为「已取消」，不会计入压缩率，也不会把进度强行显示成 100%。
- 再次点击「开始转换」继续失败或取消的项目；「重试失败」只处理失败项。
- 所有项目都已完成或智能跳过时，再次开始会询问是否按当前设置重新处理。
- 扫描或转换期间，添加、移除、清空和转换设置会暂时锁定；关闭窗口会先停止任务再退出。
- 预览页的「打开输出文件夹」可定位选中图片的输出目录；未生成输出时打开原图目录。

指定的输出文件夹位于输入文件夹内部时，后续文件夹扫描会排除该输出子目录。
已加入列表的图片保留不变；显式选择该目录或其中的图片仍可处理。

### 设置项建议

| 选项 | 建议 |
|---|---|
| **格式** | 保持 `WebP`；需要兼容老软件时才改 JPEG/PNG |
| **质量** | 网页用 **75–85** 最划算；存档用 90–95 |
| **无损模式** | 支持 WebP / PNG；PNG 开启后禁用调色板量化。JPEG / AVIF 不提供此选项 |
| **智能模式** | 只保留体积更小的转换结果；要求每张输入都有目标格式文件时，请关闭 |
| **输出位置** | 默认「与原图放在一起」；批量处理建议选一个单独的输出文件夹 |
| **保留子文件夹结构** | 处理整个项目目录时勾选 |
| **覆盖已有输出** | 默认**不勾**；勾选后替换已有输出，本批输入及并发重名任务仍会自动避让 |
| **透明区域填充背景色** | 转 JPEG 时必要；转 WebP 一般不用勾 |
| **最长边** | 填 `0` 表示不缩放；例如填 `1920` 可批量限制宽度 |

PNG 的质量低于 100 且未勾选无损时，会使用调色板量化减少颜色。
背景色、最长边和 CLI 数值参数填写错误时会在开始前提示，不会静默改成默认值。

---

## 命令行用法

打包好的程序也能当命令行工具使用：

```bash
# 把整个文件夹转成 WebP，质量 80，输出到 out/
WebPForge --cli -i ./照片 -o ./out -q 80

# 递归处理并保留子文件夹结构
WebPForge --cli -i ./相册 -o ./webp --keep -q 75

# 无损 + 限制最长边 1920
WebPForge --cli -i ./原图 -o ./large --lossless --max-edge 1920

# 用源码运行同理
python webp_converter.py --cli -i ./照片 -o ./out -q 80
```

### 参数一览

| 参数 | 说明 |
|---|---|
| `--cli` | 命令行模式（不打开界面） |
| `-i, --input` | 输入文件 / 文件夹 / 通配符，可多个 |
| `-o, --outdir` | 输出目录（省略时与原图同目录；`-o .` 明确指当前工作目录） |
| `-q, --quality` | 质量 1–100，默认 80 |
| `-f, --format` | 输出格式：`webp`(默认) / `png` / `jpeg` / `avif` |
| `--lossless` | WebP / PNG 无损编码；JPEG / AVIF 使用此参数会报错 |
| `--keep` | 保留子文件夹结构 |
| `--overwrite` | 覆盖已有输出，保护本批全部输入与同批并发输出（默认自动改名） |
| `--flatten` | 透明区域填充背景色 |
| `--bg` | 填充色，默认 `#ffffff` |
| `--max-edge` | 限制最长边像素，0 = 不缩放 |
| `--smaller-only` | 仅当结果更小才写入 |
| `--no-recursive` | 不递归子文件夹 |
| `-j, --workers` | 并发线程数（默认自动） |
| `--json` | JSON 汇总及逐文件结果，包含实际输出路径、状态、大小与错误 |
| `--selftest [REPORT]` | 环境与转换自检，可指定报告文件路径 |

`Ctrl+C` 会请求停止任务并清理尚未发布的结果。
退出码：`0` 全部成功或智能跳过，`1` 未找到输入或运行环境错误，`2` 参数错误，
`3` 部分文件失败，`130` 存在取消项。
JSON 保留原有汇总字段，并增加 `cancelled` 与 `items`；每项状态为
`ok` / `skipped` / `failed` / `cancelled`，没有生成输出时 `output` 为 `null`。
Windows 下 CLI 的标准输出和错误输出统一使用 UTF-8，支持管道与文件重定向。

---

## 从源码运行

```bash
git clone https://github.com/K-zhaochao/WebPForge.git
cd WebPForge
python -m pip install pillow
python webp_converter.py          # 打开界面
python webp_converter.py --selftest
```

需要 Python **3.8+**，且必须带 **tkinter**（python.org 官方安装包自带；Linux 上通常是 `python3-tk`）。

---

## 自己打包

### Windows

```powershell
powershell -ExecutionPolicy Bypass -File .\build_windows.ps1
```

产物：`dist\WebPForge.exe`（单文件）与 `release\WebPForge-Windows.zip`

### macOS

```bash
chmod +x build_macos.sh
./build_macos.sh
```

产物：`dist/WebPForge.app` 与 `dist/WebPForge.dmg`

> macOS 应用必须在 macOS 上编译。不想本地搭环境的话，直接推一个 tag，让 GitHub Actions 帮你出包。

### 手动打包

```bash
python -m pip install pillow pyinstaller
python tools/make_icon.py assets
pyinstaller --clean --noconfirm build.spec
```

---

## 发布新版本

推送一个版本 tag，GitHub Actions 会自动构建 Windows x64、macOS ARM64 / Intel 与网页包并创建 Release：

```bash
git tag -a v1.2.0 -m "WebPForge v1.2.0"
git push origin main
git push origin v1.2.0
```

流程见 [`.github/workflows/build.yml`](.github/workflows/build.yml)：Windows x64、macOS ARM64 与 Intel 并行打包 → 汇总为可双击的 zip → 创建 Release 并附上安装包。

自动发布 Windows x64、macOS ARM64 / Intel、Web ZIP 与 SHA256。先更新应用版本、Windows 资源版本和 CHANGELOG，与 tag 保持一致。见 [发布说明](docs/releases.md)。

Release 说明模板位于 [`.github/RELEASE_BODY.md`](.github/RELEASE_BODY.md)，
其中的版本号与下载文件名会在发布时自动替换。

---

## 项目结构

```
WebPForge/
├── webp_converter.py            # 全部逻辑：界面 + 转换引擎 + 命令行
├── README.md                    # 中文说明（默认展示）
├── README.en.md                 # English documentation
├── CHANGELOG.md                 # 版本改动与验证记录
├── LICENSE                      # MIT
├── build.spec                   # PyInstaller 打包配置
├── build_windows.ps1            # Windows 一键打包（含产物自检）
├── build_macos.sh               # macOS 一键打包（.app + .dmg）
├── convert.bat                  # Windows 命令行启动器
├── version_info.txt             # exe 版本资源信息
├── assets/                      # 图标（由 make_icon.py 生成）
├── site/                        # 官网：页面、样式、浏览器转换与自托管素材
├── docs/website.md              # 官网开发、部署与验证说明
├── .github/
│   ├── workflows/
│   │   ├── test.yml             # Windows / Linux 回归测试
│   │   ├── pages.yml            # 官网构建检查与 GitHub Pages 自动部署
│   │   ├── build.yml            # 自动打包 Windows + Mac ARM64 / Intel + Web 并发布 Release
│   │   └── build-intel.yml      # Intel 单独构建备用入口
│   └── RELEASE_BODY.md          # Release 说明模板
├── tests/                       # 转换、文件保护、CLI 与真实 GUI 回归测试
└── tools/
    ├── build_site.py            # 无第三方依赖的官网构建与链接检查
    ├── prepare_site_assets.py   # 开发时更新样图、字体及分享图
    ├── make_icon.py             # 生成 .ico / .icns 图标
    ├── make_testdata.py         # 生成测试图片（含中文名/透明/动图/损坏文件）
    ├── stress_test.py           # 并发安全压力测试
    ├── test_gui_flow.py         # 界面交互链路测试
    ├── test_gui_launch.py       # 界面启动测试
    ├── test_packaged.py         # EXE 自检、JSON 重定向与四种输出格式测试
    ├── diag_gui.py              # 界面诊断
    └── find_window.py           # 定位程序窗口（验证打包产物）
```

---

## 测试

```bash
python -m unittest discover -s tests -v      # 全部回归测试（GUI 需要桌面环境）
python webp_converter.py --selftest          # 环境 + 转换自检
python tools/make_testdata.py _testdata      # 造测试图
python tools/stress_test.py _stress          # 并发安全测试（72 个同名冲突文件）
python tools/test_gui_flow.py               # 真实窗口：扫描、预览、停止、继续、失败重试
python tools/test_gui_launch.py             # 主线程窗口启动与正常关闭
python tools/test_packaged.py dist/WebPForge.exe  # 打包后验证（当前 Pillow 须支持 AVIF）
```

回归测试使用临时目录并自动清理，不需要提前生成 `_testdata`。
无桌面的 Linux 可用 `xvfb-run -a python -m unittest discover -s tests -v`；
未提供显示服务时 GUI 测试会明确跳过。`test.yml` 在 Windows / Linux、Python 3.8 / 3.13 上运行测试。

---

## 常见问题

**Q：为什么转换后文件反而变大了？**
A：原图可能已经是 WebP，或本身就是高压缩的 JPEG。保持「智能模式」勾选即可自动跳过这类文件。

**Q：透明的 PNG 转完变成白底了？**
A：WebP **支持**透明，默认会保留。只有你勾了「透明区域填充背景色」或输出格式选了 JPEG 才会丢透明。

**Q：GIF 动图会变成静态图吗？**
A：转成 WebP 时保留全部帧、每帧时长和循环设置；没有循环标记的 GIF 播放一次。
转成 PNG / JPEG / AVIF 时目前只输出首帧，转换结果会注明。

**Q：会不会覆盖我原来的图片？**
A：默认只新增文件，重名自动改为 `名字(1).webp`。即使开启「覆盖已有输出」，
本批所有输入图片也受保护；已有输出会在编码成功后才被替换，失败或取消时保留旧文件。

**Q：要处理几千张图片，要多久？**
A：程序按 CPU 核心数自动并发。1000 张普通照片通常在 1–3 分钟内完成。

**Q：程序联网吗？**
A：完全不联网。所有处理都在本机完成，不会有任何图片被上传。

**Q：Windows 双击没反应？**
A：少数杀毒软件会拦截新生成的 exe，请加入白名单；或先用命令行 `WebPForge.exe --selftest` 检查
（结果会写到 exe 同目录的 `WebPForge_selftest.txt`）。

**Q：macOS 提示「已损坏，无法打开」？**
A：这是 Gatekeeper 对未签名应用的提示。执行 `xattr -cr WebPForge.app` 即可解决。

---

## 许可

[MIT License](LICENSE) · 可自由使用、修改与分发
