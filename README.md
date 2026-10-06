<div align="center">

# WebPForge

**批量图片转 WebP 的桌面工具 · 双击即用 · 无需安装 Python**

[![Build & Release](https://github.com/K-zhaochao/WebPForge/actions/workflows/build.yml/badge.svg)](https://github.com/K-zhaochao/WebPForge/actions/workflows/build.yml)
[![Release](https://img.shields.io/github/v/release/K-zhaochao/WebPForge?color=3ac0d6&label=release)](https://github.com/K-zhaochao/WebPForge/releases/latest)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-6f7cff)

**中文** · [English](README.en.md)

把一堆 JPG / PNG / BMP / GIF / TIFF 拖进去，点一下「开始转换」，就全部变成体积更小的 WebP。

</div>

---

## 下载

前往 [**Releases**](https://github.com/K-zhaochao/WebPForge/releases/latest) 下载对应系统的压缩包，解压后直接双击运行：

| 系统 | 文件 |
|---|---|
| Windows 10/11 (x64) | `WebPForge-<版本>-Windows-x64.zip` → 双击 `WebPForge.exe` |
| macOS（Apple Silicon / M 系列） | `WebPForge-<版本>-macOS-ARM64.zip` → 双击 `WebPForge.app` |
| macOS（Intel） | 见下方说明 ↓ |

> **Intel Mac 用户**：GitHub 的 Intel 构建机（`macos-13`）正在被下线，排队时间极长，
> 因此 Intel 包改为**手动触发构建**，放在 Release 里会拖垮整个发布流程。
> 需要 Intel 版时，到 [Actions → Build macOS Intel (manual)](https://github.com/K-zhaochao/WebPForge/actions/workflows/build-intel.yml)
> 点 **Run workflow**，构建完成后在该次运行的 Artifacts 里下载 `WebPForge-macOS-Intel.zip`。
> 或者直接在 Intel Mac 上执行 `./build_macos.sh` 自行打包。

> 程序未做代码签名，首次运行会有系统提示，属正常现象：
> - **Windows**：SmartScreen 提示 →「更多信息」→「仍要运行」
> - **macOS**：右键点击 App →「打开」→ 再点「打开」（或执行 `xattr -cr WebPForge.app`）

---

## 功能特点

| 能力 | 说明 |
|---|---|
| 批量转换 | 一次添加成百上千张图片，多线程并发转换 |
| 拖拽添加 | Windows 下直接把文件/文件夹拖进窗口即可 |
| 保留画质 | 可调质量 1–100，也可开启**无损模式** |
| 保留透明 | PNG 的透明通道不会丢失 |
| 纠正方向 | 自动处理手机照片的 EXIF 旋转标记 |
| 保留动画 | 动图 GIF 转成**动态 WebP**，帧和循环都在 |
| 智能模式 | 若转换后反而更大，自动保留原图，避免越转越糊 |
| 绝不覆盖 | 遇到重名自动改名 `名字(1).webp`，永不丢文件 |
| 保留结构 | 可选择重建子文件夹层级 |
| 缩放限制 | 可指定「最长边不超过 N 像素」批量压尺寸 |
| 中文友好 | 中文文件名、中文路径完全支持 |
| 纯离线 | 不联网、不上传，图片只在本机处理 |

支持的输入格式：JPG / JPEG / PNG / BMP / GIF / TIFF / TGA / ICO / WebP / AVIF 及 Pillow 支持的其它格式。
输出格式：**WebP（默认）**，也支持 PNG / JPEG / AVIF。

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

### 设置项建议

| 选项 | 建议 |
|---|---|
| **格式** | 保持 `WebP`；需要兼容老软件时才改 JPEG/PNG |
| **质量** | 网页用 **75–85** 最划算；存档用 90–95 |
| **无损模式** | 只在需要像素级还原时开（文件会大很多） |
| **智能模式** | **建议保持勾选**，避免已压缩过的图被二次压缩 |
| **输出位置** | 默认「与原图放在一起」；批量处理建议选一个单独的输出文件夹 |
| **保留子文件夹结构** | 处理整个项目目录时勾选 |
| **覆盖同名文件** | 默认**不勾**（自动改名更安全） |
| **透明区域填充背景色** | 转 JPEG 时必要；转 WebP 一般不用勾 |
| **最长边** | 填 `0` 表示不缩放；例如填 `1920` 可批量限制宽度 |

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
| `-o, --outdir` | 输出目录（默认与原图同目录） |
| `-q, --quality` | 质量 1–100，默认 80 |
| `-f, --format` | 输出格式：`webp`(默认) / `png` / `jpeg` / `avif` |
| `--lossless` | 无损编码 |
| `--keep` | 保留子文件夹结构 |
| `--overwrite` | 覆盖同名文件（默认自动改名） |
| `--flatten` | 透明区域填充背景色 |
| `--bg` | 填充色，默认 `#ffffff` |
| `--max-edge` | 限制最长边像素，0 = 不缩放 |
| `--smaller-only` | 仅当结果更小才写入 |
| `--no-recursive` | 不递归子文件夹 |
| `-j, --workers` | 并发线程数（默认自动） |
| `--json` | 以 JSON 输出结果，便于脚本调用 |
| `--selftest` | 自检：验证环境与转换功能是否正常 |

---

## 从源码运行

```bash
git clone https://github.com/K-zhaochao/WebPForge.git
cd REPO
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

推送一个版本 tag，GitHub Actions 会自动构建三个平台并创建 Release：

```bash
git tag v1.0.0
git push origin v1.0.0
```

流程见 [`.github/workflows/build.yml`](.github/workflows/build.yml)：Windows 与 Apple Silicon 并行打包 → 汇总为可双击的 zip → 创建 Release 并附上安装包。

Intel 版由 [`.github/workflows/build-intel.yml`](.github/workflows/build-intel.yml) 手动触发构建，
**故意不放进自动发布流程**——GitHub 的 Intel 构建机排队时间经常超过 30 分钟，
把它挂进 `release` 的依赖会让整个版本发不出去。

Release 说明模板位于 [`.github/RELEASE_BODY.md`](.github/RELEASE_BODY.md)，
其中的版本号与下载文件名会在发布时自动替换。

---

## 项目结构

```
WebPForge/
├── webp_converter.py            # 全部逻辑：界面 + 转换引擎 + 命令行
├── README.md                    # 中文说明（默认展示）
├── README.en.md                 # English documentation
├── LICENSE                      # MIT
├── build.spec                   # PyInstaller 打包配置
├── build_windows.ps1            # Windows 一键打包（含产物自检）
├── build_macos.sh               # macOS 一键打包（.app + .dmg）
├── convert.bat                  # Windows 命令行启动器
├── version_info.txt             # exe 版本资源信息
├── assets/                      # 图标（由 make_icon.py 生成）
├── .github/
│   ├── workflows/
│   │   ├── build.yml            # 自动打包 Windows + Apple Silicon 并发布 Release
│   │   └── build-intel.yml      # Intel 版手动构建（避免拖慢发布）
│   └── RELEASE_BODY.md          # Release 说明模板
└── tools/
    ├── make_icon.py             # 生成 .ico / .icns 图标
    ├── make_testdata.py         # 生成测试图片（含中文名/透明/动图/损坏文件）
    ├── stress_test.py           # 并发安全压力测试
    ├── test_gui_flow.py         # 界面交互链路测试
    ├── test_gui_launch.py       # 界面启动测试
    ├── diag_gui.py              # 界面诊断
    └── find_window.py           # 定位程序窗口（验证打包产物）
```

---

## 测试

```bash
python webp_converter.py --selftest          # 环境 + 转换自检
python tools/make_testdata.py _testdata      # 造测试图
python tools/stress_test.py _stress          # 并发安全测试（72 个同名冲突文件）
python tools/test_gui_flow.py                # 界面链路测试
```

---

## 常见问题

**Q：为什么转换后文件反而变大了？**
A：原图可能已经是 WebP，或本身就是高压缩的 JPEG。保持「智能模式」勾选即可自动跳过这类文件。

**Q：透明的 PNG 转完变成白底了？**
A：WebP **支持**透明，默认会保留。只有你勾了「透明区域填充背景色」或输出格式选了 JPEG 才会丢透明。

**Q：GIF 动图会变成静态图吗？**
A：不会。转成 WebP 时会保留全部帧、每帧时长和循环次数。

**Q：会不会覆盖我原来的图片？**
A：不会。程序只**新增** `.webp` 文件，从不删除或改写原图；遇到同名文件会自动改名为 `名字(1).webp`。

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
