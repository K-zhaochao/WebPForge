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
  if (request.mode === "navigate" && url.pathname === new URL(APP_ROOT).pathname) {
    event.respondWith(caches.open(CACHE_NAME).then(async (cache) =>
      (await cache.match(APP_ROOT)) || fetch(request)));
    return;
  }
  if (!PUBLIC_URLS.has(url.href)) return;
  event.respondWith(caches.open(CACHE_NAME).then(async (cache) =>
    (await cache.match(request)) || fetch(request)));
});
