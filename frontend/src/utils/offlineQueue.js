/**
 * Gestor de Cola Offline con IndexedDB, IDs Idempotentes y Background Sync para AquaPulse PWA (Fase 5).
 */

const DB_NAME = 'aquapulse_pwa_offline_v1';
const STORE_NAME = 'measurements_queue';
const DB_VERSION = 1;

/**
 * Abre o inicializa la base de datos IndexedDB local.
 */
export function openOfflineDB() {
  return new Promise((resolve, reject) => {
    if (typeof window === 'undefined' || !window.indexedDB) {
      return reject(new Error('IndexedDB no está disponible en este entorno.'));
    }

    const request = window.indexedDB.open(DB_NAME, DB_VERSION);

    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'client_uuid' });
      }
    };

    request.onsuccess = (event) => {
      resolve(event.target.result);
    };

    request.onerror = (event) => {
      reject(event.target.error || new Error('Error al abrir IndexedDB'));
    };
  });
}

/**
 * Genera un UUID v4 criptográfico o fallback con entropía aleatoria.
 */
export function generateClientUUID() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'offline-' + Date.now() + '-' + Math.random().toString(36).substring(2, 11);
}

/**
 * Encola una medición en IndexedDB para envío posterior cuando haya conexión.
 */
export async function enqueueOfflineMeasurement(tankId, measurementData) {
  try {
    const db = await openOfflineDB();
    const clientUuid = measurementData.client_uuid || generateClientUUID();
    const payloadWithId = {
      ...measurementData,
      client_uuid: clientUuid,
      timestamp: measurementData.timestamp || new Date().toISOString()
    };

    const record = {
      client_uuid: clientUuid,
      tank_id: tankId ? Number(tankId) : null,
      payload: payloadWithId,
      queued_at: new Date().toISOString(),
      retry_count: 0
    };

    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite');
      const store = tx.objectStore(STORE_NAME);
      const req = store.put(record);
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });

    console.info(`[AquaPulse PWA] Medición encolada offline (ID: ${clientUuid})`);

    // Intentar registrar Background Sync en el Service Worker si está soportado
    if (typeof navigator !== 'undefined' && 'serviceWorker' in navigator && 'SyncManager' in window) {
      try {
        const reg = await navigator.serviceWorker.ready;
        if (reg && reg.sync) {
          await reg.sync.register('sync-offline-measurements');
        }
      } catch (syncErr) {
        console.debug('[AquaPulse PWA] Background Sync no registrado (fallback a evento online):', syncErr);
      }
    }

    notifyQueueUpdated();
    return record;
  } catch (err) {
    console.error('[AquaPulse PWA] Error al encolar medición offline:', err);
    throw err;
  }
}

/**
 * Obtiene todas las mediciones pendientes encoladas.
 */
export async function getPendingOfflineMeasurements() {
  try {
    const db = await openOfflineDB();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readonly');
      const store = tx.objectStore(STORE_NAME);
      const req = store.getAll();
      req.onsuccess = () => resolve(req.result || []);
      req.onerror = () => reject(req.error);
    });
  } catch (err) {
    console.error('[AquaPulse PWA] Error al leer cola offline:', err);
    return [];
  }
}

/**
 * Elimina una medición sincronizada con éxito de la cola local.
 */
export async function removeOfflineMeasurement(clientUuid) {
  try {
    const db = await openOfflineDB();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite');
      const store = tx.objectStore(STORE_NAME);
      const req = store.delete(clientUuid);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
    notifyQueueUpdated();
  } catch (err) {
    console.error(`[AquaPulse PWA] Error al eliminar medición de cola (${clientUuid}):`, err);
  }
}

/**
 * Notifica a los componentes visuales mediante un CustomEvent.
 */
async function notifyQueueUpdated() {
  if (typeof window !== 'undefined') {
    const queue = await getPendingOfflineMeasurements();
    window.dispatchEvent(new CustomEvent('offline-queue-updated', { detail: { count: queue.length, queue } }));
  }
}

/**
 * Procesa la cola offline transmitiendo las mediciones pendientes al backend.
 */
export async function flushOfflineQueue(sendFn) {
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    console.debug('[AquaPulse PWA] Sin conexión a internet. Postergando vaciado de cola offline.');
    return { synced: 0, pending: (await getPendingOfflineMeasurements()).length };
  }

  const queue = await getPendingOfflineMeasurements();
  if (!queue.length) return { synced: 0, pending: 0 };

  console.info(`[AquaPulse PWA] Vaciando cola offline (${queue.length} mediciones pendientes)...`);
  let syncedCount = 0;

  for (const item of queue) {
    try {
      if (sendFn) {
        await sendFn(item.tank_id, item.payload);
      } else {
        // Importación dinámica para evitar ciclos de import
        const { recordTankMeasurement } = await import('../api');
        await recordTankMeasurement(item.tank_id, item.payload);
      }
      await removeOfflineMeasurement(item.client_uuid);
      syncedCount++;
      console.info(`[AquaPulse PWA] Medición sincronizada con éxito (${item.client_uuid})`);
    } catch (err) {
      console.warn(`[AquaPulse PWA] Error al sincronizar medición ${item.client_uuid}:`, err);
      // Si el error no es de red (ej. tanque no existe 404), evitar bucle infinito aumentando retry
      if (err.message && !err.message.includes('fetch') && !err.message.includes('Network')) {
        item.retry_count = (item.retry_count || 0) + 1;
        if (item.retry_count > 5) {
          console.error(`[AquaPulse PWA] Descartando medición corrupta tras 5 reintentos (${item.client_uuid})`);
          await removeOfflineMeasurement(item.client_uuid);
        }
      }
      break; // Detener bucle si se detecta falla de conectividad
    }
  }

  notifyQueueUpdated();
  return { synced: syncedCount, pending: (await getPendingOfflineMeasurements()).length };
}

// Escuchar evento online del navegador para auto-sincronizar
if (typeof window !== 'undefined') {
  window.addEventListener('online', () => {
    console.info('[AquaPulse PWA] Conexión restaurada. Auto-sincronizando mediciones encoladas...');
    flushOfflineQueue();
  });

  if (typeof navigator !== 'undefined' && 'serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', (event) => {
      if (event.data && event.data.type === 'SYNC_OFFLINE_MEASUREMENTS') {
        flushOfflineQueue();
      }
    });
  }
}
