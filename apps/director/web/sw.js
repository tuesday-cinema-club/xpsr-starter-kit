// Caches the app shell so the brief, shots and audit open with no network.
// API calls and media always go to the network.
const CACHE = "xpsr-director-v2";
const SHELL = ["/", "/index.html", "/app.css", "/app.js", "/api.js", "/data.js", "/pack.js", "/zip.js",
  "/resources.html", "/resources.js", "/resources.css", "/library.html", "/library.js", "/manifest.webmanifest", "/icon.svg",
  "/fonts/inter-tight-latin-500-normal.woff2", "/fonts/inter-tight-latin-700-normal.woff2",
  "/fonts/inter-tight-latin-800-normal.woff2", "/fonts/jetbrains-mono-latin-400-normal.woff2",
  "/fonts/jetbrains-mono-latin-700-normal.woff2"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;
  // Network first, so a redeploy shows up at once; the cache covers offline.
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(e.request, copy)); }
        return res;
      })
      .catch(() => caches.match(e.request, { ignoreSearch: true }).then((r) => r || caches.match("/index.html"))),
  );
});
