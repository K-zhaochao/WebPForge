import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import { english, normalize, translate } from "../site/messages.js";

const source = (name) => readFile(new URL(`../site/${name}`, import.meta.url), "utf8");

test("every Chinese static text and accessibility label has an English translation", async () => {
  const html = (await source("index.html")).replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/g, "");
  const strings = html.split(/<[^>]+>/).concat(
    [...html.matchAll(/(?:aria-label|alt|title|aria-valuetext|content)="([^"]*)"/g)].map((match) => match[1]),
  );
  for (const text of strings) {
    if (!/[\u4e00-\u9fff]/.test(text) || /@@/.test(text)) continue;
    assert.ok(Object.hasOwn(english, normalize(text)), `Missing translation: ${normalize(text)}`);
  }
});

test("runtime errors, installation guidance and savings labels are localized", async () => {
  for (const file of ["app.js", "pwa.js", "platform.js", "image-codec.js", "image-input.js"]) {
    const strings = [...(await source(file)).matchAll(/"([^"\n]*[\u4e00-\u9fff][^"\n]*)"/g)];
    for (const [, text] of strings) assert.ok(Object.hasOwn(english, normalize(text)), `${file}: ${text}`);
  }
  assert.equal(translate("这是一张动画图片。请使用桌面版转换，以保留所有动画帧。", "en"),
    "This is an animated image. Use the desktop edition to preserve every frame.");
});

test("interpolation preserves user filenames without interpreting HTML or translation keys", () => {
  const name = "山野 <img src=x> {quality}.jpg";
  assert.equal(translate("{name}，质量 {quality} 的 WebP 转换结果", "en", {name, quality: 80}),
    `${name}, converted WebP at quality 80`);
  assert.equal(translate("{name}原图", "zh-CN", {name}), `${name}原图`);
  assert.equal(translate("原图占左侧 {left}%，WebP 占右侧 {right}%", "en", {left: 30, right: 70}),
    "Original on the left 30%, WebP on the right 70%");
  assert.equal(translate("download.webp", "en"), "download.webp");
});

test("rendered release versions and download labels remain localized across releases", () => {
  assert.equal(translate("v1.2.3 已发布", "en"), "v1.2.3 is here");
  assert.equal(translate("下载 WebPForge v1.2.3 macOS Apple Silicon 版，ZIP 14.8 MB", "en"),
    "Download WebPForge v1.2.3 for macOS Apple Silicon, ZIP 14.8 MB");
  assert.equal(translate("免费下载", "zh-CN"), "免费下载");
});

async function boot(preferences, dark, denied = false) {
  const root = {dataset: {}, classList: {add() {}}};
  const meta = {setAttribute(name, value) { this[name] = value; }};
  vm.runInNewContext(await source("preferences.js"), {
    document: {documentElement: root, querySelector: () => meta},
    localStorage: {getItem(key) { if (denied) throw new Error("Storage disabled"); return preferences[key]; }},
    matchMedia: () => ({matches: dark}),
  });
  return {root, meta};
}

test("theme and language preferences are applied before CSS and survive system changes", async () => {
  const {root, meta} = await boot({"webpforge-theme": "light", "webpforge-language": "en"}, true);
  assert.equal(root.dataset.theme, "light");
  assert.equal(root.lang, "en");
  assert.equal(meta.content, "#f5f5ef");
  assert.equal((await boot({"webpforge-theme": "dark"}, false)).root.dataset.theme, "dark");
});

test("first visit follows system theme, invalid preferences and denied storage degrade gracefully", async () => {
  for (const denied of [false, true]) {
    const {root, meta} = await boot({"webpforge-theme": "invalid", "webpforge-language": "invalid"}, true, denied);
    assert.equal(root.dataset.theme, "dark");
    assert.equal(root.lang, "zh-CN");
    assert.equal(meta.content, "#171a17");
  }
  assert.equal((await boot({}, false)).root.dataset.theme, "light");
});

test("navigation follows document order and mobile breakpoint agrees with its controller", async () => {
  const html = await source("index.html");
  const nav = html.match(/<nav class="primary-nav"[\s\S]*?<\/nav>/)[0];
  const ids = [...nav.matchAll(/href="#([^"]+)"/g)].map((match) => match[1]);
  assert.deepEqual(ids, ["playground", "features", "download", "faq"]);
  for (let i = 1; i < ids.length; i++) assert.ok(html.indexOf(`id="${ids[i - 1]}"`) < html.indexOf(`id="${ids[i]}"`));
  assert.match(await source("app.js"), /max-width: 1040px/);
  assert.match(await source("styles.css"), /@media \(max-width: 1040px\)/);
  assert.ok(html.indexOf('src="preferences.js"') < html.indexOf('href="styles.css"'));
});
