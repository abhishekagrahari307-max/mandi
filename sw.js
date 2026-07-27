const CACHE_NAME = 'up-mandi-v1';
const ASSETS = [
  './index.html',
  './manifest.json',
  './data/latest.json',
  './data/history.json',
  './data/weather.json',
  'https://cdn.tailwindcss.com',
  'https://unpkg.com/lucide@latest',
  'https://cdn.jsdelivr.net/npm/chart.js'
];

// Install Event
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      console.log('Caching assets...');
      return cache.addAll(ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate Event
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.map(key => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch Event
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request).then(cachedResponse => {
      // Return cached response if found, else fetch from network
      return cachedResponse || fetch(event.request).then(networkResponse => {
        // Dynamically cache new requests if needed
        return networkResponse;
      });
    }).catch(() => {
      // Offline fallback
      if (event.request.url.includes('index.html')) {
        return caches.match('./index.html');
      }
    })
  );
});
