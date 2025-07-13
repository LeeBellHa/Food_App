const CACHE_NAME = 'fridge-helper-v1';
const PRECACHE_URLS = [
  '/', '/upload', '/results', '/style', '/chat',
  '/static/style.css',
  '/static/manifest.json',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png'
];

// 설치 시 필수 자원 프리캐시
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(PRECACHE_URLS))
  );
  self.skipWaiting();
});

// activate 시 구버전 캐시 정리
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(key => key !== CACHE_NAME)
            .map(key => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

// fetch 핸들러
self.addEventListener('fetch', event => {
  const req = event.request;

  // 1) CSS (destination: 'style') → network-first
  if (req.destination === 'style') {
    event.respondWith(
      fetch(req)
        .then(networkRes => {
          // 네트워크에 성공하면 캐시도 최신화
          const copy = networkRes.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(req, copy));
          return networkRes;
        })
        .catch(() => caches.match(req))
    );
    return;
  }

  // 2) 페이지 내비게이션(HTML) → network-first
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then(networkRes => {
          const copy = networkRes.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(req, copy));
          return networkRes;
        })
        .catch(() => caches.match(req).then(cached => cached || caches.match('/')))
    );
    return;
  }

  // 3) 기타 자원 (이미지, JS, 아이콘 등) → cache-first
  event.respondWith(
    caches.match(req)
      .then(cached => cached || fetch(req))
  );
});
