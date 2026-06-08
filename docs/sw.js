/* Minimal PWA service worker: cache the app shell, network-first for navigation. */
const CACHE = "ajs-v1";
const SHELL = ["./", "./index.html", "./manifest.webmanifest", "./icon.svg"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  const req = e.request;
  // Never cache Anthropic API calls.
  if (req.url.includes("api.anthropic.com")) return;
  if (req.mode === "navigate") {
    // Network-first so a fresh pipeline build is picked up; fall back to cache offline.
    e.respondWith(
      fetch(req).then(r => { caches.open(CACHE).then(c => c.put("./index.html", r.clone())); return r; })
        .catch(() => caches.match("./index.html"))
    );
    return;
  }
  e.respondWith(caches.match(req).then(r => r || fetch(req)));
});
