# 发布新版本

官网：[webp.royi.net](https://webp.royi.net/)。默认在线转换，手机安装 PWA；桌面版通过 GitHub Release 下载。

## 日常官网更新

修改 site/ 后测试、提交并推送 main，Pages 自动部署。仅官网修改不需要 tag。

```bash
node --test tests/site-*.test.mjs
python -X utf8 -m unittest discover -s tests -v
python tools/build_site.py
```

## 发布桌面新版本

以未来 v1.2.0 为例，使用尚未发布的版本号：

1. 更新 webp_converter.py 的 APP_VERSION、version_info.txt 的数字与字符串版本、CHANGELOG。macOS 从精确 tag 或应用版本读取。
2. 测试通过后先提交并推送 main，再创建 tag：

```bash
git add .
git commit -m "Release WebPForge v1.2.0"
git push origin main
git tag -a v1.2.0 -m "WebPForge v1.2.0"
git push origin v1.2.0
```

3. [Build & Release](https://github.com/K-zhaochao/WebPForge/actions/workflows/build.yml) 并行构建 Windows x64、macOS ARM64、macOS Intel。tag 与 APP_VERSION 不一致会终止；Windows 程序通过打包自检。
4. 三个平台成功后，合并 ZIP、构建对应版本网页包，生成 SHA256SUMS.txt 和 release-manifest.json，创建正式 Release。手动运行只构建，不发布。
5. [Deploy official website](https://github.com/K-zhaochao/WebPForge/actions/workflows/pages.yml) 在发布工作流完成后同步最新下载地址。这覆盖了 GITHUB_TOKEN 创建的 Release 不触发其他工作流的情况。
6. 发布后下载 release-manifest.json，保存为 site/release.json 并提交，使本地离线快照与线上一致。

## 下载校验

Windows PowerShell：

```powershell
Get-FileHash .\WebPForge-1.2.0-Windows-x64.zip -Algorithm SHA256
```

macOS / Linux：

```bash
shasum -a 256 WebPForge-1.2.0-macOS-ARM64.zip
# Linux 可一次核验同目录所有文件
sha256sum -c SHA256SUMS.txt
```

与 Release 的 SHA256SUMS.txt 对比。网页包通过 HTTP 服务打开，不直接用 file://，见包内 START-HERE.txt。

## 失败与回滚

- 平台失败：查看日志，修复后先手动构建验证。已发布 tag 保持不变，修复版用新版本号。
- 官网失败：旧版继续在线，修复后手动运行 Pages 工作流。
- 页面回滚：对问题提交执行 git revert，推送 main 重新部署。
- 桌面回滚：从历史 Release 下载对应系统版本，替换前保存自己的转换输出。

## 域名与 HTTPS

site/CNAME 为 webp.royi.net，Pages 来源为 GitHub Actions。证书签发完成后启用 Enforce HTTPS；手机安装依赖 HTTPS。此流程不修改 DNS。

参考：[PWA 安装条件](https://developer.mozilla.org/en-US/docs/Web/Progressive_web_apps/Guides/Making_PWAs_installable)、[GitHub runner 标签](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)。
