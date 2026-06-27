// Knowledge Garden Service Worker
// Bump CACHE version on every release to invalidate stale entries.
const CACHE = 'knowledge-book-v3';

self.addEventListener('install', e => {
    e.waitUntil(
        caches.open(CACHE).then(c => c.addAll(['./']))
    );
    self.skipWaiting();
});

self.addEventListener('activate', e => {
    e.waitUntil(
        caches.keys()
            .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
            .then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', e => {
    const req = e.request;
    if (req.method !== 'GET') return;
    const url = new URL(req.url);
    // Cache same-origin GET only (skip cross-origin like CDN fonts).
    if (url.origin !== self.location.origin) return;
    // 哪些路径值得缓存: assets/ (book JSONs + search index + Q&A dense) + index.html + root
    const isCacheable =
        url.pathname.includes('/assets/') ||
        url.pathname.endsWith('.html') ||
        url.pathname === '/' || url.pathname.endsWith('/');
    if (!isCacheable) return; // 非 cacheable 请求走默认网络
    e.respondWith(
        caches.match(req).then(cached => {
            if (cached) return cached;
            return fetch(req).then(resp => {
                if (resp && resp.ok) {
                    const clone = resp.clone();
                    caches.open(CACHE).then(c => c.put(req, clone)).catch(() => {});
                }
                return resp;
            }).catch(() => {
                // 离线 fallback: SPA app shell
                return caches.match('./');
            });
        })
    );
});
