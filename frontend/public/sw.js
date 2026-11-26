const CACHE_NAME = 'aquapulse-cache-v8';
const APP_SHELL = ['/', '/index.html', '/manifest.json', '/icon-192.png', '/icon-512.png', '/icon-maskable-512.png', '/apple-touch-icon.png'];

self.addEventListener('install', (event) => {
  // Guardar el esqueleto de la app para poder abrirla sin conexión.
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL)).catch(() => {})
  );
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
  const request = event.request;
  const url = new URL(request.url);

  // SEGURIDAD PWA (Fase 5): NUNCA almacenar ni servir desde caché peticiones a /api/*
  // (datos privados de usuario), ni nada que no sea GET del propio dominio.
  if (request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api')) {
    return;
  }

  // Navegación: red primero; sin conexión, el index.html guardado (la SPA enruta sola).
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put('/index.html', copy)).catch(() => {});
          return response;
        })
        .catch(() => caches.match('/index.html'))
    );
    return;
  }

  // Archivos estáticos (JS, CSS, íconos): red primero y copia en caché para uso offline.
  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(request, copy)).catch(() => {});
        }
        return response;
      })
      .catch(() => caches.match(request))
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

  const title = data.title || 'AquaReef 🌊';
  const body = data.body || 'Tienes una nueva actualización en AquaReef.';
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
      // Si la ventana de AquaReef ya está abierta, enfocarla y navegar
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
