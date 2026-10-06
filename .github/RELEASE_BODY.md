## WebPForge

批量把图片转换为 WebP 的桌面工具 —— **双击即可运行**，无需安装 Python 或任何依赖。

A desktop batch image → WebP converter. Just double-click to run — no Python, no dependencies.

> 说明文档：[**中文**](https://github.com/OWNER/REPO#readme) · [**English**](https://github.com/OWNER/REPO/blob/main/README.en.md)

### 下载

| 系统 | 文件 | 说明 |
|---|---|---|
| Windows 10/11 (x64) | `WebPForge-Windows-x64.zip` | 解压后双击 `WebPForge.exe` |
| macOS（Apple Silicon / M 系列） | `WebPForge-macOS-ARM64.zip` | 解压后双击 `WebPForge.app` |
| macOS（Intel） | `WebPForge-macOS-Intel.zip` | 解压后双击 `WebPForge.app`（若本次未提供，见下） |

> Intel 版依赖 GitHub 的 Intel 构建机，该镜像正在被逐步下线，因此个别版本可能不包含 Intel 包。
> 遇到这种情况，可在 Intel Mac 上执行 `./build_macos.sh` 自行打包，步骤见 README。

### 首次打开提示

程序未做代码签名，首次运行可能出现系统提示，属正常现象：

- **Windows**：出现 SmartScreen 提示时，点「更多信息」→「仍要运行」。
- **macOS**：提示「无法验证开发者」时，**右键点击 App → 打开 → 再点打开**（只需一次）；
  或执行 `xattr -cr WebPForge.app`。

### 主要功能

- **批量转换**：多线程并发，一次处理成百上千张
- **拖拽添加**（Windows），文件夹递归扫描
- **可调质量 / 无损模式**，保留透明通道与 EXIF 旋转
- **动图 GIF → 动态 WebP**，保留帧、每帧时长与循环次数
- **智能模式**：转换后反而更大就保留原图，避免越转越糊
- **绝不覆盖原图**，重名自动改名 `名字(1).webp`
- **完全离线**，图片不出本机

### 命令行用法

打包好的程序也能当命令行工具用：

```bash
WebPForge --cli -i ./照片 -o ./out -q 80 --keep
```

### 给项目点个 Star ⭐

如果这个工具对你有帮助，欢迎到 [GitHub 仓库](https://github.com/OWNER/REPO) 点个 Star，
或在程序界面里点「⭐ 关于 / 项目主页」直接跳转。问题与建议请提到
[Issues](https://github.com/OWNER/REPO/issues)。

详见 [中文说明](https://github.com/OWNER/REPO#readme) ·
[English docs](https://github.com/OWNER/REPO/blob/main/README.en.md)。
