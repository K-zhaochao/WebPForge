/* Rendered by tools/build_site.py. Only public application files are cached. */
const CACHE_PREFIX = "webpforge-";
const CACHE_NAME = CACHE_PREFIX + "@@CACHE_VERSION@@";
const PRECACHE = @@PRECACHE_URLS@@;
const APP_ROOT = new URL("./", self.location).href;
const PUBLIC_URLS = new Set(PRECACHE.map((path) => new URL(path, APP_ROOT).href));

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE)));
  // Keep the current app and worker together until the user chooses to update.
});
self.addEventListener("message", (event) => {
  if (event.data?.type === "SKIP_WAITING") self.skipWaiting();
});
self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    for (const key of await caches.keys()) {
      if (key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME) await caches.delete(key);
    }
    await self.clients.claim();
  })());
});
self.addEventListener("fetch", (event) => {
  const { request } = event;
  const url = new URL(request.url);
  if (request.method !== "GET" || url.origin !== self.location.origin) return;
  // Never cache local uploads, blobs, arbitrary paths, API calls or downloads.
  if (request.mode === "navigate" && [new URL(APP_ROOT).pathname, new URL("index.html", APP_ROOT).pathname].includes(url.pathname)) {
    // Fresh HTML discovers the next fingerprinted worker; cached HTML remains
    // available offline. Static resources are immutable, content-addressed URLs.
    event.respondWith((async () => {
      let timer;
      try {
        const response = await Promise.race([
          fetch(request, { cache: "no-cache" }),
          new Promise((_, reject) => { timer = setTimeout(() => reject(new Error("Navigation timeout")), 3500); }),
        ]);
        if (response.ok) return response;
        throw new Error("Navigation unavailable");
      } catch {
        const cache = await caches.open(CACHE_NAME);
        const cached = await cache.match(APP_ROOT);
        if (cached) return cached;
        return fetch(request);
      } finally { clearTimeout(timer); }
    })());
    return;
  }
  if (!PUBLIC_URLS.has(url.href)) return;
  event.respondWith(caches.open(CACHE_NAME).then(async (cache) =>
    (await cache.match(request)) || fetch(request)));
});
