# WebPForge 官网

公开地址：<https://webp.royi.net/>

官网以暖白、墨黑、荧光绿为主色，使用大字排版、摄影卡片和可操作的图片对比展示产品。
首屏的示例数据来自实际文件大小；在线体验则根据当前浏览器生成的 WebP 计算结果。
两者的编码器不同，文件大小可能略有差异。

## 本地开发

需要 Python 3.9+（推荐 3.13）；构建只使用标准库，没有前端运行时依赖。
Node.js 22+ 仅用于图片校验模块的自动测试，无需 `npm install`。

```bash
python tools/build_site.py
node --test tests/site-image.test.mjs
python -m http.server 4173 --bind 127.0.0.1 --directory _site
```

用浏览器打开 <http://127.0.0.1:4173/>。修改后重新运行构建并刷新页面。
`site/index.html` 包含构建时替换的 Release 占位符，请预览 `_site/`。
浏览器模块使用 `.js` 后缀，兼容 Windows 的 Python HTTP 服务 MIME 配置。

| 文件 | 用途 |
| --- | --- |
| `site/index.html` | 内容、语义结构、SEO、下载链接模板 |
| `site/styles.css` | 排版、响应式布局、焦点状态、减少动画偏好 |
| `site/app.js` | 导航、示例选择、本地读取、画质控制、实际编码与下载 |
| `site/image-codec.js` | 解码前格式/尺寸/动画校验、文件名与体积计算 |
| `site/release.json` | 本地构建使用的已验证 Release 快照 |
| `site/assets/` | 摄影、缩略图、字体、许可与实测样图清单 |
| `tools/build_site.py` | 替换版本数据，检查链接、图片大小和锚点，生成 `_site/` |
| `tools/prepare_site_assets.py` | 开发时生成摄影尺寸、缩略图、分享图与字体子集 |
| `.github/workflows/pages.yml` | 测试、构建、上传 Pages 产物与部署 |

`_site/` 和 `_site_qa/` 是被 Git 忽略的本地构建/验证目录。构建脚本只会替换仓库内
准确的 `_site/` 路径，并拒绝符号链接和越界路径。

## 在线体验的边界

- 通过文件选择器读取本机文件；图片不发送到服务器，也不写入浏览器持久存储。
- 按文件签名检查静态 JPEG、PNG 和 WebP，不依赖扩展名或上传声明的 MIME 类型。
- 在完整解码前检查 20 MB、1,600 万像素及单边 8,192 像素限制，超限明确建议使用桌面版，不自动缩图。
- 拒绝 GIF、APNG 和动态 WebP，避免默默丢掉动画帧。
- 保留透明通道，按浏览器解码后的照片方向绘制。导出图重新编码，不保留原文件元数据。
- 使用 Canvas `toBlob('image/webp', quality)`，并验证实际输出 MIME。浏览器不支持时给出说明，不把 PNG 假装成 WebP 下载。
- 画质 100 仍然是有损 WebP；无损、动画和批量属于桌面版功能。
- 显示真实文件大小，包括结果变大的情况，不保证所有图片都变小。
- 编码串行执行，快速操作会跳过过期请求；较早结束的回调不能覆盖新图片或新画质的结果。
- 切换图片和结果时回收 Object URL。无效输入会保留上一次可用结果，文件选择取消不会清空图片。

## 自动部署

仓库 Settings → Pages 的构建来源使用 **GitHub Actions**。部署文件为
`.github/workflows/pages.yml`，触发方式为：

1. `main` 上官网、官网测试、构建脚本或部署工作流发生变更；
2. 发布正式 Release；GITHUB_TOKEN 创建的 Release 通过 Build & Release 的 workflow_run 完成事件触发官网刷新；
3. 在 Actions → Deploy official website 手动运行。

构建先运行图片处理、PWA 与部署契约测试，再通过公开 GitHub API 获取最新 Release 的 Windows x64
与 macOS ARM64 ZIP 及其真实大小。两个安装包齐备后才继续发布。
因此官网不会指向空安装包，也不需要浏览者每次请求 GitHub API。
GitHub API 暂时不可用时部署会明确失败，已上线版本保持可用。

构建工作仅有仓库与 Pages 读取权限，部署工作使用 `pages: write` 和 `id-token: write`。
不需要额外的部署密码或个人令牌。生产地址为 `https://webp.royi.net/`；CNAME、canonical、分享、robots 和 sitemap 均使用此域名。资源与 PWA scope 采用相对路径。

```bash
# 在本地模拟部署时的 Release 刷新；不会改动源文件中的快照
python tools/build_site.py --refresh-release
```

更新 `site/release.json` 可让后续离线开发与当前正式版保持一致。无需为只修改官网创建软件版本 tag。

## 素材维护

样图与字体来源、许可见 [`site/assets/NOTICE.md`](../site/assets/NOTICE.md)。
生产网页不依赖第三方图片或字体 CDN。图片下载与字体生成仅发生在开发工具中。

```bash
python -m pip install pillow
python tools/prepare_site_assets.py          # 更新图片、缩略图和分享预览
python tools/prepare_site_assets.py --fonts  # 同时更新开放字体与标题文字子集
```

修改中文界面或提示后应重新生成字体子集，覆盖正文、标题与运行时提示。英文和数字优先使用 Manrope；未知文件名用系统字体兜底。
分享图优先使用 Windows 自带字体进行版式合成；其他系统会生成纯摄影分享图。
仓库中已提交可直接发布的分享图，CI 不需要重新生成。

## 2026-10-08 验证记录

- 静态构建检查通过：83 个 HTML/CSS/模块引用、页内锚点、示例图片的实际字节数。
- Node.js 7 项测试通过：真实格式、透明 PNG、动画标记、损坏内容、尺寸与体积上限、压缩增减、中文文件名。
- 浏览器实测：三张样图、质量 1/80/100、快速切换图片与画质、对比滑杆两端及实际拖动、结果变大的显示。
- 实际上传 320 × 200 透明 PNG 并下载 WebP，用 Pillow 确认仍为 RGBA、透明值范围 0–128。
- EXIF 方向为 6 的 80 × 120 JPEG，下载结果正确为 120 × 80 WebP。
- GIF、APNG、动态 WebP、损坏 JPEG、伪造超大尺寸 PNG、超过 20 MB 的文件都显示对应说明，并保留原先可用结果。
- 画质改变尚未完成时选择损坏图片，会保留原图并按最新画质继续生成可下载结果，不会停留在过期状态。
- 检查桌面与手机布局、移动导航收起、键盘操作、FAQ 和返回顶部。
- 检查 320、360、390、540、768、1024、1440 像素视口，没有页面横向溢出。

上述交互验证使用 Chromium 内核的内置浏览器。Safari、Firefox 的真实设备表现需在相应设备上另行验证；不支持编码时已有可见提示。


## 手机安装与离线更新

手机采用 PWA，而非原生 APK / IPA。`manifest.webmanifest` 配置独立窗口与图标；`pwa.js` 按设备提供安装指引。iOS 使用 Safari「分享 → 添加到主屏幕」。

`sw.js` 仅缓存公开应用文件，用户图片和结果只存在于内存 Blob URL。首次需联网，成功后显示离线就绪；清理浏览器数据会清除缓存。

缓存版本按渲染页面、脚本、样图、字体和下载信息的内容哈希生成。新 worker 不自动接管正在转换的页面，用户保存结果后点击更新才重载；关闭全部旧窗口也可完成正常更新。维护步骤见 [releases.md](releases.md)。
