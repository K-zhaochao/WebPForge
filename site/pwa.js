import { setText } from "./interface.js";
import { detectPlatform, installInstructions } from "./platform.js";

const button = document.querySelector("#install-app");
const offlineStatus = document.querySelector("#offline-status");
const dialog = document.querySelector("#install-dialog");
const platform = detectPlatform(navigator.userAgent, navigator.platform, navigator.maxTouchPoints);
const installed = () => matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
const recommendation = document.querySelector("#device-recommendation");
const messages = {
  windows: "当前设备：Windows。可在线用、安装轻应用，或下载 x64 桌面版。",
  macos: "当前设备：Mac。桌面版请按芯片选择 Apple Silicon 或 Intel。",
  android: "当前设备：Android。推荐直接在线转换，或安装轻应用到主屏幕。",
  ios: "当前设备：iPhone / iPad。推荐在线转换，或用 Safari 添加到主屏幕。",
  other: "在线版支持手机和电脑；Linux 等系统可使用在线版或浏览器轻应用。",
};
setText(recommendation, messages[platform]);
document.querySelector(`[data-platform="${platform}"]`)?.classList.add("is-recommended");
setText(document.querySelector("#install-instructions"), installInstructions(platform));
let installPrompt = null;
let registration = null;
let updateRequested = false;

function syncInstall() {
  setText(button, installed() ? "已安装 · 查看使用说明" : installPrompt ? "安装 WebPForge" : "安装到手机 / 电脑");
}
function syncOffline() {
  const ready = Boolean(navigator.serviceWorker?.controller || registration?.active);
  setText(offlineStatus, ready
    ? navigator.onLine ? "离线资源已就绪 · 断网也能转换，图片不上传。" : "当前离线 · 仍可选择图片并转换。"
    : "首次打开需联网，资源缓存完成后可离线转换。");
}
window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  installPrompt = event;
  syncInstall();
});
window.addEventListener("appinstalled", () => { installPrompt = null; syncInstall(); });
matchMedia("(display-mode: standalone)").addEventListener("change", syncInstall);
button.addEventListener("click", async () => {
  if (!installPrompt) { dialog.showModal(); return; }
  const prompt = installPrompt;
  installPrompt = null;
  button.disabled = true;
  try { await prompt.prompt(); await prompt.userChoice; }
  catch { dialog.showModal(); }
  finally { button.disabled = false; syncInstall(); }
});
dialog.addEventListener("click", (event) => { if (event.target === dialog) dialog.close(); });
window.addEventListener("online", syncOffline);
window.addEventListener("offline", syncOffline);
syncInstall();

if ("serviceWorker" in navigator && window.isSecureContext) {
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    syncOffline();
    if (updateRequested) window.location.reload();
  });
  const showUpdate = () => {
    if (registration.waiting && navigator.serviceWorker.controller) document.querySelector("#app-update").hidden = false;
  };
  document.querySelector("#update-app").addEventListener("click", () => {
    if (!registration?.waiting) return;
    updateRequested = true;
    registration.waiting.postMessage({ type: "SKIP_WAITING" });
  });
  const workerURL = document.querySelector('meta[name="webpforge-worker"]').content;
  navigator.serviceWorker.register(workerURL, { updateViaCache: "none" }).then((value) => {
    registration = value;
    showUpdate();
    syncOffline();
    registration.addEventListener("updatefound", () => {
      const worker = registration.installing;
      worker?.addEventListener("statechange", () => {
        showUpdate();
        syncOffline();
      });
    });
    navigator.serviceWorker.ready.then(syncOffline);
  }).catch(() => {
    setText(offlineStatus, "离线资源暂未就绪，仍可在线转换；联网后重新打开可再次准备。");
  });
} else {
  setText(offlineStatus, "当前环境使用在线版；离线安装请通过 HTTPS 官网在新版浏览器中打开。");
}
