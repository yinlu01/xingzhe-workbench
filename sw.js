// 行者工作台 Service Worker
// v4 缓存策略（2026-08-24 修复）：HTML/JSON 一律网络优先，只有图标走缓存。
// 旧版对 HTML/JSON 采用缓存优先，导致桌面 App 更新后仍显示旧页面 —— 已废除。
const CACHE_NAME = 'xingzhe-dashboard-v4';
const STATIC_ASSETS = [
  '/icons/icon-192.png',
  '/icons/icon-512.png'
];
// 网络优先：所有 HTML 页面与 JSON 数据（内容会持续更新，必须每次取最新）
const isNetworkFirst = url =>
  url.pathname.endsWith('.html') ||
  url.pathname.endsWith('.json') ||
  url.pathname === '/' ||
  url.pathname === '/sw.js';

// ===== INSTALL =====
self.addEventListener('install', event => {
  console.log('[SW] Installing...');
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      console.log('[SW] Caching static assets');
      return cache.addAll(STATIC_ASSETS).catch(err => {
        console.warn('[SW] Some assets failed to cache:', err.message);
      });
    })
  );
  self.skipWaiting();
});

// ===== ACTIVATE =====
self.addEventListener('activate', event => {
  console.log('[SW] Activating...');
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// ===== FETCH =====
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);

  if (isNetworkFirst(url)) {
    // 网络优先：页面与数据永远拿最新，失败才回退缓存
    event.respondWith(
      fetch(event.request).then(response => {
        if (response.ok) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      }).catch(() => caches.match(event.request))
    );
    return;
  }

  // 其余静态资源（图标等）缓存优先
  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;
      return fetch(event.request).then(response => {
        if (response.ok && response.type === 'basic') {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
        }
        return response;
      }).catch(() => {
        if (event.request.mode === 'navigate') {
          return caches.match('/mac-dashboard.html');
        }
        return new Response('Offline', { status: 503 });
      })
    })
  );
});

// ===== PUSH NOTIFICATION =====
self.addEventListener('push', event => {
  let data = { title: '行者工作台', body: '有新的提醒', icon: '/icons/icon-192.png' };
  
  if (event.data) {
    try {
      const payload = event.data.json();
      data = { ...data, ...payload };
    } catch {
      data.body = event.data.text();
    }
  }

  const options = {
    body: data.body,
    icon: data.icon || '/icons/icon-192.png',
    badge: '/icons/icon-192.png',
    vibrate: [200, 100, 200],
    tag: data.tag || 'default',
    data: { url: data.url || '/life-dashboard.html' },
    actions: [
      { action: 'open', title: '打开工作台' },
      { action: 'dismiss', title: '知道了' }
    ],
    requireInteraction: true
  };

  event.waitUntil(self.registration.showNotification(data.title, options));
});

// ===== NOTIFICATION CLICK =====
self.addEventListener('notificationclick', event => {
  event.notification.close();
  
  if (event.action === 'dismiss') return;

  const url = event.notification.data?.url || '/life-dashboard.html';
  
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clientsArr => {
      // If a window is already open, focus it
      for (const client of clientsArr) {
        if (client.url.includes('life-dashboard') && 'focus' in client) {
          return client.focus().then(() => client.navigate(url));
        }
      }
      // Otherwise open a new window
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});

// ===== PERIODIC SYNC (daily reading reminder) =====
self.addEventListener('periodicsync', event => {
  if (event.tag === 'reading-reminder') {
    event.waitUntil(
      self.registration.showNotification('📖 今日读书提醒', {
        body: '现在是最佳阅读时间，打开工作台看看今天的读书任务吧',
        icon: '/icons/icon-192.png',
        badge: '/icons/icon-192.png',
        vibrate: [200, 100, 200],
        tag: 'reading-daily',
        requireInteraction: true,
        actions: [
          { action: 'open', title: '去读书' },
          { action: 'dismiss', title: '稍后' }
        ]
      })
    );
  }
});

console.log('[SW] Service Worker ready');
