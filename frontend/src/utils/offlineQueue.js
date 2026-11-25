/**
 * Gestor de Cola Offline con IndexedDB, IDs Idempotentes y Background Sync para AquaReef PWA (Fase 5).
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

    console.info(`[AquaReef PWA] Medición encolada offline (ID: ${clientUuid})`);

    // Intentar registrar Background Sync en el Service Worker si está soportado. Sin await:
    // serviceWorker.ready no se resuelve nunca si no hay SW registrado (primera visita,
    // desarrollo, registro fallido) y bloquearía el guardado. El evento 'online' es el respaldo.
    if (typeof navigator !== 'undefined' && 'serviceWorker' in navigator && 'SyncManager' in window) {
      navigator.serviceWorker.ready
        .then((reg) => (reg && reg.sync ? reg.sync.register('sync-offline-measurements') : null))
        .catch((syncErr) => {
          console.debug('[AquaReef PWA] Background Sync no registrado (fallback a evento online):', syncErr);
        });
    }

    notifyQueueUpdated();
    return record;
  } catch (err) {
    console.error('[AquaReef PWA] Error al encolar medición offline:', err);
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
    console.error('[AquaReef PWA] Error al leer cola offline:', err);
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
    console.error(`[AquaReef PWA] Error al eliminar medición de cola (${clientUuid}):`, err);
  }
}

/**
 * Guarda (o reemplaza) un registro de la cola, p. ej. para persistir retry_count.
 */
async function saveQueueRecord(record) {
  try {
    const db = await openOfflineDB();
    await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite');
      const req = tx.objectStore(STORE_NAME).put(record);
      req.onsuccess = () => resolve();
      req.onerror = () => reject(req.error);
    });
  } catch (err) {
    console.error(`[AquaReef PWA] Error al actualizar medición en cola (${record.client_uuid}):`, err);
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
    console.debug('[AquaReef PWA] Sin conexión a internet. Postergando vaciado de cola offline.');
    return { synced: 0, pending: (await getPendingOfflineMeasurements()).length };
  }

  const queue = await getPendingOfflineMeasurements();
  if (!queue.length) return { synced: 0, pending: 0 };

  console.info(`[AquaReef PWA] Vaciando cola offline (${queue.length} mediciones pendientes)...`);
  let syncedCount = 0;

  // Importación dinámica para evitar ciclos de import. sendQueuedMeasurement no vuelve a
  // encolar si falla: así un error de red no se confunde con un envío exitoso.
  const { sendQueuedMeasurement, isNetworkError } = await import('../api');
  const send = sendFn || sendQueuedMeasurement;

  for (const item of queue) {
    try {
      await send(item.tank_id, item.payload);
      await removeOfflineMeasurement(item.client_uuid);
      syncedCount++;
      console.info(`[AquaReef PWA] Medición sincronizada con éxito (${item.client_uuid})`);
    } catch (err) {
      console.warn(`[AquaReef PWA] Error al sincronizar medición ${item.client_uuid}:`, err);
      // Sin red o sesión vencida: detener y reintentar en el próximo evento online / login.
      if (isNetworkError(err) || err.status === 401) {
        break;
      }
      // El servidor la rechazó (p. ej. 404 o 422): contar el reintento y guardarlo, y
      // descartarla tras 5 para no bloquear el resto de la cola.
      item.retry_count = (item.retry_count || 0) + 1;
      if (item.retry_count > 5) {
        console.error(`[AquaReef PWA] Descartando medición rechazada tras 5 reintentos (${item.client_uuid})`);
        await removeOfflineMeasurement(item.client_uuid);
      } else {
        await saveQueueRecord(item);
      }
    }
  }

  notifyQueueUpdated();
  return { synced: syncedCount, pending: (await getPendingOfflineMeasurements()).length };
}

// Escuchar evento online del navegador para auto-sincronizar
if (typeof window !== 'undefined') {
  window.addEventListener('online', () => {
    console.info('[AquaReef PWA] Conexión restaurada. Auto-sincronizando mediciones encoladas...');
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
