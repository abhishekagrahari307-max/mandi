const CACHE_NAME = 'up-mandi-v4';
const STATIC_ASSETS = [
  './manifest.json',
  'https://cdn.tailwindcss.com',
  'https://unpkg.com/lucide@latest',
  'https://cdn.jsdelivr.net/npm/chart.js'
];

// Install Event - cache only purely static libraries
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      console.log('Caching static libraries...');
      return cache.addAll(STATIC_ASSETS);
    })
  );
  self.skipWaiting();
});

// Activate Event - clean up all old cache namespaces completely
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.map(key => {
          if (key !== CACHE_NAME) {
            console.log('Clearing old cache:', key);
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch Event - Network-First for index.html, roots, and data; Cache-First for static assets
self.addEventListener('fetch', event => {
  const url = event.request.url;

  // STRICT NETWORK-FIRST STRATEGY for HTML, dynamic APIs, and pricing data JSONs
  // This guarantees that online users always see the latest code and rates instantly!
  if (
    url.endsWith('index.html') || 
    url.endsWith('/') || 
    url.endsWith('mandi/') || 
    url.includes('data/') || 
    url.includes('/api/v2/')
  ) {
    event.respondWith(
      fetch(event.request)
        .then(networkResponse => {
          // Dynamically cache the fresh network copy for offline fallback
          return caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, networkResponse.clone());
            return networkResponse;
          });
        })
        .catch(() => {
          // Serve offline fallback from cache if internet is down
          return caches.match(event.request);
        })
    );
  } else {
    // Cache-First strategy for static CDN libraries
    event.respondWith(
      caches.match(event.request).then(cachedResponse => {
        return cachedResponse || fetch(event.request);
      })
    );
  }
});
