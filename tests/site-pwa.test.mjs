import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import { detectPlatform, installInstructions } from "../site/platform.js";

test("platform detection distinguishes mobile Apple devices from desktop Mac", () => {
  assert.equal(detectPlatform("Android 16", "Linux armv8l"), "android");
  assert.equal(detectPlatform("iPhone", "iPhone"), "ios");
  assert.equal(detectPlatform("Macintosh", "MacIntel", 5), "ios");
  assert.equal(detectPlatform("Macintosh", "MacIntel", 0), "macos");
  assert.equal(detectPlatform("Windows NT 10.0", "Win32"), "windows");
  assert.equal(detectPlatform("Linux", "Linux x86_64"), "other");
  assert.match(installInstructions("ios"), /Safari.*添加到主屏幕/);
  assert.match(installInstructions("android"), /安装应用/);
});

async function workerHarness() {
  const handlers = {};
  const buckets = new Map();
  const cached = new Map([["https://webp.royi.net/", "offline-app"], ["https://webp.royi.net/app.js", "offline-script"]]);
  let precache, skipped = false, claimed = false;
  const cache = { addAll: async (urls) => { precache = urls; }, match: async (request) => cached.get(typeof request === "string" ? request : request.url) };
  const context = {
    URL, Set, setTimeout, clearTimeout,
    self: { location: new URL("https://webp.royi.net/sw.js"), addEventListener: (name, fn) => { handlers[name] = fn; },
            skipWaiting: () => { skipped = true; }, clients: { claim: async () => { claimed = true; } } },
    caches: { open: async (name) => { buckets.set(name, cache); return cache; }, keys: async () => [...buckets.keys()], delete: async (key) => buckets.delete(key) },
    fetch: async (request) => {
      if (request.mode === "navigate") throw new Error("Offline fixture");
      return `network:${request.url}`;
    },
  };
  let script = await readFile(new URL("../site/sw.js", import.meta.url), "utf8");
  script = script.replace("@@CACHE_VERSION@@", "test-version").replace("@@PRECACHE_URLS@@", '["./", "./app.js"]');
  vm.runInNewContext(script, context);
  return { handlers, buckets, context, status: () => ({ precache, skipped, claimed }) };
}

test("PWA installation caches public files and waits for explicit update", async () => {
  const harness = await workerHarness();
  let task;
  harness.handlers.install({ waitUntil: (promise) => { task = promise; } });
  await task;
  assert.deepEqual([...harness.status().precache], ["./", "./app.js"]);
  assert.equal(harness.status().skipped, false);
  harness.handlers.message({ data: { type: "OTHER" } });
  assert.equal(harness.status().skipped, false);
  harness.handlers.message({ data: { type: "SKIP_WAITING" } });
  assert.equal(harness.status().skipped, true);
});

test("worker serves app and script offline but never caches uploads or external downloads", async () => {
  const { handlers } = await workerHarness();
  let task;
  const respondWith = (promise) => { task = promise; };
  handlers.fetch({ request: { method: "GET", mode: "navigate", url: "https://webp.royi.net/?utm_source=test" }, respondWith });
  assert.equal(await task, "offline-app");
  handlers.fetch({ request: { method: "GET", mode: "cors", url: "https://webp.royi.net/app.js" }, respondWith });
  assert.equal(await task, "offline-script");
  for (const request of [
    { method: "POST", url: "https://webp.royi.net/upload" },
    { method: "GET", url: "https://github.com/a/download.zip" },
    { method: "GET", url: "blob:https://webp.royi.net/local-image" },
    { method: "GET", url: "https://webp.royi.net/private-image.png" },
  ]) {
    task = undefined;
    handlers.fetch({ request, respondWith });
    assert.equal(task, undefined);
  }
});

test("worker activation removes only old application caches", async () => {
  const harness = await workerHarness();
  harness.buckets.set("webpforge-old", {});
  harness.buckets.set("unrelated-app", {});
  let task;
  harness.handlers.activate({ waitUntil: (promise) => { task = promise; } });
  await task;
  assert.equal(harness.buckets.has("webpforge-old"), false);
  assert.equal(harness.buckets.has("unrelated-app"), true);
  assert.equal(harness.status().claimed, true);
});

test("online navigation discovers fresh HTML instead of pinning an old worker forever", async () => {
  const harness = await workerHarness();
  const response = { ok: true, content: "fresh-version-html" };
  harness.context.fetch = async () => response;
  let task;
  harness.handlers.fetch({ request: { method: "GET", mode: "navigate", url: "https://webp.royi.net/" }, respondWith: (value) => { task = value; } });
  assert.equal(await task, response);
});
