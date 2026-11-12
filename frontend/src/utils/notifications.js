/**
 * Módulo para gestión de Web Notifications API y recordatorios locales
 * para pruebas de calidad de agua y alertas de desestabilización.
 */

const STORAGE_KEY = 'aquapulse_notification_config';

export function getNotificationSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      return JSON.parse(raw);
    }
  } catch (err) {
    console.error('Error al leer configuración de notificaciones:', err);
  }
  return {
    enabled: false,
    reminderTime: '20:00', // 8:00 PM por defecto (hora típica post-laboral para tests de acuario)
    lastNotifiedDate: null,
    notifyOnWarning: true,
    notifyOnWaterChange: true
  };
}

export function saveNotificationSettings(settings) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
  } catch (err) {
    console.error('Error al guardar configuración de notificaciones:', err);
  }
}

export async function requestNotificationPermission() {
  if (!('Notification' in window)) {
    throw new Error('Tu navegador no soporta la Web Notifications API.');
  }

  const permission = await Notification.requestPermission();
  return permission;
}

export function isNotificationSupported() {
  return typeof window !== 'undefined' && 'Notification' in window;
}

export function getPermissionState() {
  if (!isNotificationSupported()) return 'unsupported';
  return Notification.permission; // 'default', 'granted', 'denied'
}

export async function sendLocalNotification(title, options = {}) {
  if (!isNotificationSupported() || Notification.permission !== 'granted') {
    return false;
  }

  const defaultOptions = {
    icon: '/favicon.svg',
    badge: '/favicon.svg',
    vibrate: [200, 100, 200],
    tag: 'aquapulse-reminder',
    renotify: true,
    ...options
  };

  // Si existe un service worker activo, usar showNotification para mejor compatibilidad PWA
  if ('serviceWorker' in navigator) {
    try {
      const reg = await navigator.serviceWorker.ready;
      if (reg && reg.showNotification) {
        await reg.showNotification(title, defaultOptions);
        return true;
      }
    } catch (err) {
      console.warn('Fallo al enviar notificación vía Service Worker, usando Notification nativa:', err);
    }
  }

  // Fallback a Notification estándar
  try {
    new Notification(title, defaultOptions);
    return true;
  } catch (err) {
    console.error('Error al instanciar Notification:', err);
    return false;
  }
}

/**
 * Evalúa las predicciones del sistema y dispara la notificación si:
 * 1. Están habilitadas y autorizadas.
 * 2. La hora actual coincide o superó la hora elegida.
 * 3. No se ha notificado hoy todavía.
 * 4. La alcalinidad está cayendo o requiere medición hoy.
 */
export async function evaluateScheduledReminder(predictions) {
  const settings = getNotificationSettings();
  if (!settings.enabled || getPermissionState() !== 'granted') {
    return false;
  }

  if (!predictions) return false;

  const now = new Date();
  const todayStr = now.toISOString().slice(0, 10); // YYYY-MM-DD

  // Evitar enviar más de una notificación al día
  if (settings.lastNotifiedDate === todayStr) {
    return false;
  }

  // Comparar hora actual (HH:MM) con la hora configurada por el usuario
  const [targetHour, targetMinute] = settings.reminderTime.split(':').map(Number);
  const currentHour = now.getHours();
  const currentMinute = now.getMinutes();

  const currentTimeInMinutes = currentHour * 60 + currentMinute;
  const targetTimeInMinutes = targetHour * 60 + targetMinute;

  // Si aún no es la hora de alerta seleccionada
  if (currentTimeInMinutes < targetTimeInMinutes) {
    return false;
  }

  // Comprobar si las predicciones indican que debe medir hoy
  const alk = predictions.alkalinity;
  const wc = predictions.water_change_prediction;

  let shouldAlert = false;
  let alertTitle = '🌊 AquaPulse: Recordatorio de Medición';
  let alertBody = '';

  // Condición A: Alcalinidad cayendo hacia el límite (<= 3 días o estado de advertencia)
  if (alk && (alk.days_remaining_safe !== null && alk.days_remaining_safe <= 3.0)) {
    shouldAlert = true;
    alertTitle = '⚠️ Alerta de Alcalinidad: ¡Medir Hoy!';
    alertBody = `Tu dKH desciende a -${alk.daily_consumption_rate || '0.2'} dKH/día. Alcanzará el límite seguro (7.5 dKH) en ~${alk.days_remaining_safe} días. Realiza un test hoy para calibrar tu dosificación.`;
  } else if (alk && (alk.status === 'critical_below_safe' || alk.status === 'warning_approaching')) {
    shouldAlert = true;
    alertTitle = '⚠️ Desestabilización de KH Detectada';
    alertBody = alk.alert_message || 'Tu alcalinidad requiere atención inmediata hoy.';
  } else if (wc && wc.urgency === 'immediate') {
    shouldAlert = true;
    alertTitle = '🚨 Cambio de Agua Requerido';
    alertBody = `Nitratos acumulados (${wc.current_nitrate_ppm} ppm). Se recomienda realizar el cambio de agua del ${wc.suggested_percentage}% hoy.`;
  }

  if (shouldAlert) {
    const sent = await sendLocalNotification(alertTitle, {
      body: alertBody,
      data: { url: '/' }
    });

    if (sent) {
      settings.lastNotifiedDate = todayStr;
      saveNotificationSettings(settings);
      return true;
    }
  }

  return false;
}
