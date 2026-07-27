const CACHE_NAME = 'up-mandi-v12';
const STATIC_ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './data/latest.json',
  './data/source_prices.json',
  './data/history.json',
  './data/state_prices.json',
  './data/mandis.json',
  './data/auction.json',
  './data/laws.json',
  './data/benchmarks.json',
  './data/sources.json',
  'https://cdn.tailwindcss.com',
  'https://unpkg.com/lucide@latest',
  'https://cdn.jsdelivr.net/npm/chart.js',
  'https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js'
];

// Install Event - cache best-effort assets without blocking activation.
// CDN requests can fail on some networks; that must never keep an old broken
// service worker alive or stop the dashboard JavaScript from loading fresh data.
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      console.log('Caching app shell and libraries...');
      return Promise.allSettled(
        STATIC_ASSETS.map(asset => cache.add(asset))
      );
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
  const request = event.request;
  const url = request.url;

  // The Cache API only accepts GET requests: cache.put() with a POST rejects
  // with "TypeError: Invalid request method POST", which would reject the whole
  // respondWith() promise and make POSTs such as /api/v2/alerts/subscribe and
  // /api/v2/update look like network failures. Let non-GET traffic go straight
  // to the network, untouched.
  if (request.method !== 'GET') {
    return;
  }

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
      fetch(request)
        .then(networkResponse => {
          // fetch() also resolves for 404/500 and for opaque cross-origin
          // replies. Caching those would overwrite a good offline copy with an
          // error page, so only store a genuinely successful same-origin
          // response. The response is still returned to the page either way.
          const isCacheable = networkResponse &&
            networkResponse.ok &&
            networkResponse.type !== 'opaque';

          if (!isCacheable) {
            return networkResponse;
          }

          const copy = networkResponse.clone();
          // Cache in the background: a storage failure (for example a full
          // quota) must never block the fresh response the user is waiting on.
          event.waitUntil(
            caches.open(CACHE_NAME)
              .then(cache => cache.put(request, copy))
              .catch(() => undefined)
          );
          return networkResponse;
        })
        .catch(() =>
          // Serve offline fallback from cache if internet is down.
          caches.match(request).then(cached => cached || Response.error())
        )
    );
  } else {
    // Cache-First strategy for static CDN libraries
    event.respondWith(
      caches.match(request).then(cachedResponse => cachedResponse || fetch(request))
    );
  }
});
