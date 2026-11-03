/* UP Mandi offline cache — lightweight, stable-cache-key implementation.
 *
 * The old worker precached latest.json and source_prices.json (about 29 MB),
 * and the page appended a new timestamp query string every two minutes. That
 * created an unlimited series of full-size cache entries and could exhaust
 * memory/storage on mobile browsers. The page now loads one compact
 * dashboard.json from a stable URL; large canonical snapshots are never cached.
 */
const CACHE_NAME = 'up-mandi-v22';
const MAX_CACHEABLE_BYTES = 3 * 1024 * 1024;
const SCOPE_URL = new URL(self.registration.scope);

const SMALL_ASSETS = [
  './',
  './index.html',
  './manifest.json',
  './images/icon-192.png',
  './images/icon-512.png',
  './data/dashboard.json',
  './data/history.json',
  './data/state_prices.json',
  './data/mandis.json',
  './data/auction.json',
  './data/laws.json',
  './data/benchmarks.json',
  './data/sources.json',
  './data/basti_division.json'
];

const CDN_ASSETS = [
  'https://cdn.tailwindcss.com',
  'https://unpkg.com/lucide@0.263.0',
  'https://cdn.jsdelivr.net/npm/chart.js@4.4.1'
];

const LARGE_DATA_FILENAMES = [
  'latest.json',
  'latest.json.bak',
  'source_prices.json',
  'source_prices.json.bak',
  'source_prices_backup.json',
  'datagov_raw_records.json'
];

const SMALL_DATA_PATHS = new Set(
  SMALL_ASSETS
    .filter(asset => asset.includes('/data/'))
    .map(asset => new URL(asset, SCOPE_URL).pathname)
);
const SHELL_PATHS = new Set(
  SMALL_ASSETS
    .filter(asset => !asset.includes('/data/'))
    .map(asset => new URL(asset, SCOPE_URL).pathname)
);
const CDN_ASSET_URLS = new Set(CDN_ASSETS);

function stableCacheRequest(request) {
  const url = new URL(request.url);
  // Strip cache-busting query strings so ?t=... can never create a new cache
  // entry for the same resource.
  url.search = '';
  return new Request(url.toString(), { method: 'GET' });
}

function isLargeLegacyData(pathname) {
  return LARGE_DATA_FILENAMES.some(name => pathname.endsWith(`/data/${name}`));
}

function isCacheableResponse(request, response) {
  const url = new URL(request.url);
  if (url.origin !== SCOPE_URL.origin) return false;
  if (isLargeLegacyData(url.pathname)) return false;
  if (!SMALL_DATA_PATHS.has(url.pathname) && !SHELL_PATHS.has(url.pathname)) return false;
  const length = Number(response.headers.get('content-length') || 0);
  return !length || length <= MAX_CACHEABLE_BYTES;
}

async function cacheResponse(request, networkResponse) {
  // A 404/500 or an opaque cross-origin reply must never overwrite the good
  // offline copy. Keep the explicit ok/type guard next to the cache write.
  const isCacheableNetworkResponse = Boolean(networkResponse) &&
    networkResponse.ok &&
    networkResponse.type !== 'opaque';
  if (!isCacheableNetworkResponse || !isCacheableResponse(request, networkResponse)) return;
  const cache = await caches.open(CACHE_NAME);
  await cache.put(stableCacheRequest(request), networkResponse.clone());
}

async function networkFirst(event, request) {
  try {
    const response = await fetch(request);
    // Cache in the background; a quota failure must never delay fresh data.
    if (response && response.ok) {
      event.waitUntil(cacheResponse(request, response).catch(() => undefined));
    }
    return response;
  } catch (error) {
    const cache = await caches.open(CACHE_NAME);
    const cached = await cache.match(stableCacheRequest(request));
    if (cached) return cached;
    if (request.mode === 'navigate') {
      const shell = await cache.match(new URL('./index.html', SCOPE_URL).toString());
      if (shell) return shell;
    }
    return Response.error();
  }
}

async function cacheFirst(event, request) {
  const cache = await caches.open(CACHE_NAME);
  const cached = await cache.match(request);
  if (cached) return cached;
  const response = await fetch(request);
  if (response && (response.ok || response.type === 'opaque')) {
    event.waitUntil(cache.put(request, response.clone()).catch(() => undefined));
  }
  return response;
}

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => Promise.allSettled(
      [...SMALL_ASSETS, ...CDN_ASSETS].map(asset => {
        const url = new URL(asset, SCOPE_URL).toString();
        return cache.add(new Request(url, { mode: asset.startsWith('http') ? 'no-cors' : 'cors' }));
      })
    ))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key)));

    // Purge any oversized entries that an older worker may have written.
    const cache = await caches.open(CACHE_NAME);
    const requests = await cache.keys();
    await Promise.all(requests.map(request => {
      const url = new URL(request.url);
      const isOversizedData = url.origin === SCOPE_URL.origin && isLargeLegacyData(url.pathname);
      const isUnstableDataKey = url.origin === SCOPE_URL.origin && url.pathname.includes('/data/') && url.search;
      return (isOversizedData || isUnstableDataKey) ? cache.delete(request) : undefined;
    }));
  })());
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  const isSameOrigin = url.origin === SCOPE_URL.origin;
  const isDataRequest = isSameOrigin && url.pathname.includes('/data/');
  const isShellRequest = isSameOrigin && (
    request.mode === 'navigate' ||
    url.pathname.endsWith('.html') ||
    SHELL_PATHS.has(url.pathname)
  );

  if (isDataRequest || isShellRequest || url.pathname.includes('/api/v2/')) {
    event.respondWith(networkFirst(event, request));
  } else if (CDN_ASSET_URLS.has(url.toString()) || url.hostname === 'cdn.tailwindcss.com' || url.hostname === 'unpkg.com' || url.hostname === 'cdn.jsdelivr.net') {
    event.respondWith(cacheFirst(event, request));
  }
  // Everything else goes straight to the network untouched.
});
