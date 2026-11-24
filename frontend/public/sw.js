const CACHE_NAME = 'aquapulse-cache-v6';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  // SEGURIDAD PWA (Fase 5): NUNCA almacenar ni servir desde caché peticiones a /api/* (datos privados de usuario)
  if (event.request.url.includes('/api/') || event.request.mode === 'navigate') {
    return;
  }
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});

// ==============================================================================
// 🔄 BACKGROUND SYNC: COLA OFFLINE DE MEDICIONES (FASE 5)
// ==============================================================================

self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-offline-measurements') {
    event.waitUntil(
      self.clients.matchAll({ includeUncontrolled: true, type: 'window' }).then((clients) => {
        clients.forEach((client) => {
          client.postMessage({ type: 'SYNC_OFFLINE_MEASUREMENTS' });
        });
      })
    );
  }
});

// ==============================================================================
// 🔔 EVENTOS DE NOTIFICACIONES PUSH (VAPID)
// ==============================================================================

self.addEventListener('push', (event) => {
  let data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data = { body: event.data.text() };
    }
  }

  const title = data.title || 'AquaPulse 🌊';
  const body = data.body || 'Tienes una nueva actualización en AquaPulse.';
  const icon = data.icon || '/icon-192.png';
  const badge = data.badge || '/icon-192.png';
  const url = data.url || '/';
  const tag = data.tag || 'aquapulse-alert';

  const options = {
    body: body,
    icon: icon,
    badge: badge,
    vibrate: [200, 100, 200],
    data: { url: url },
    tag: tag,
    renotify: true
  };

  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || '/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      // Si la ventana de AquaPulse ya está abierta, enfocarla y navegar
      for (const client of windowClients) {
        if ('focus' in client) {
          if ('navigate' in client && targetUrl) {
            client.navigate(targetUrl);
          }
          return client.focus();
        }
      }
      // Si no está abierta, abrir una nueva ventana
      if (clients.openWindow) {
        return clients.openWindow(targetUrl);
      }
    })
  );
});
