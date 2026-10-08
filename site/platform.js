export function detectPlatform(userAgent = "", platform = "", touchPoints = 0) {
  if (/Android/i.test(userAgent)) return "android";
  if (/iPhone|iPad|iPod/i.test(userAgent) || (platform === "MacIntel" && touchPoints > 1)) return "ios";
  if (/Win/i.test(platform) || /Windows/i.test(userAgent)) return "windows";
  if (/Mac/i.test(platform) || /Macintosh/i.test(userAgent)) return "macos";
  return "other";
}

export function installInstructions(platform) {
  if (platform === "ios") return "用 Safari 打开 webp.royi.net，点「分享」，选择「添加到主屏幕」，再点「添加」。如未看到该选项，请先在 Safari 中打开本站。";
  if (platform === "android") return "用 Chrome 或 Edge 打开 webp.royi.net，在右上角菜单选择「安装应用」或「添加到主屏幕」。若正使用微信等内置浏览器，请先选择「在浏览器打开」。";
  return "用 Chrome 或 Edge 打开本站，点击地址栏中的安装图标，或在浏览器菜单中选择「安装 WebPForge」。其他浏览器可继续在线使用。";
}
