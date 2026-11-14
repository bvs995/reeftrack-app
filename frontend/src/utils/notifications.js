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
 * Rangos seguros de referencia estándar para parámetros de arrecife (Reef).
 */
export const RANGOS_SEGUROS_DEFAULT = {
  'Fosfato': { min: 0.02, max: 0.08 },
  'Alcalinidad': { min: 7.5, max: 8.5 },
  'Calcio': { min: 400, max: 450 },
  'Magnesio': { min: 1250, max: 1450 },
  'Nitrato': { min: 2.0, max: 15.0 },
  'pH': { min: 8.1, max: 8.4 },
  'Temperatura': { min: 24.5, max: 26.5 },
  'Salinidad': { min: 34.0, max: 36.0 },
  // Claves normalizadas en minúsculas y códigos técnicos
  'fosfato': { min: 0.02, max: 0.08 },
  'po4': { min: 0.02, max: 0.08 },
  'alcalinidad': { min: 7.5, max: 8.5 },
  'dkh': { min: 7.5, max: 8.5 },
  'kh': { min: 7.5, max: 8.5 },
  'alkalinity': { min: 7.5, max: 8.5 },
  'calcio': { min: 400, max: 450 },
  'ca': { min: 400, max: 450 },
  'calcium': { min: 400, max: 450 },
  'magnesio': { min: 1250, max: 1450 },
  'mg': { min: 1250, max: 1450 },
  'magnesium': { min: 1250, max: 1450 },
  'nitrato': { min: 2.0, max: 15.0 },
  'no3': { min: 2.0, max: 15.0 },
  'nitrate': { min: 2.0, max: 15.0 },
  'ph': { min: 8.1, max: 8.4 },
  'temperatura': { min: 24.5, max: 26.5 },
  'temp': { min: 24.5, max: 26.5 },
  'temperature': { min: 24.5, max: 26.5 },
  'salinidad': { min: 34.0, max: 36.0 },
  'salinity': { min: 34.0, max: 36.0 }
};

/**
 * Evalúa las predicciones contra los rangos seguros para generar alertas urgentes.
 * 1. NUEVA VALIDACIÓN: Verifica si el valor actual YA está fuera de rango ('Peligro').
 * 2. VALIDACIÓN EXISTENTE: Verifica si la proyección a 3 días saldrá del rango ('Advertencia').
 * 
 * @param {Array|Object} predictions Lista de parámetros [{ nombre, medicionReal, proyeccion3Dias }] o respuesta predictiva
 * @param {Object} [rangosSeguros=RANGOS_SEGUROS_DEFAULT] Mapeo de rangos seguros { min, max }
 * @returns {Array<{tipo: string, parametro: string, mensaje: string, accion: string}>} Alertas urgentes
 */
export function evaluateScheduledReminder(predictions, rangosSeguros = RANGOS_SEGUROS_DEFAULT) {
  let alertasUrgentes = [];
  if (!predictions) return alertasUrgentes;

  const rangos = rangosSeguros || RANGOS_SEGUROS_DEFAULT;

  // Normalizar datos si predictions es un objeto (PredictionResponse de API) o un Array de parámetros
  const items = Array.isArray(predictions)
    ? predictions
    : Object.entries(predictions)
        .filter(([key, val]) => val && typeof val === 'object' && ('current_value' in val || 'medicionReal' in val))
        .map(([key, val]) => ({
          nombre: val.nombre || val.parameter || key,
          medicionReal: val.medicionReal !== undefined ? val.medicionReal : val.current_value,
          proyeccion3Dias: val.proyeccion3Dias !== undefined ? val.proyeccion3Dias : val.projected_value_3d
        }));

  items.forEach(parametro => {
    if (!parametro || !parametro.nombre) return;
    const valorActual = parametro.medicionReal;
    const rango = rangos[parametro.nombre] || rangos[parametro.nombre.toLowerCase()];

    // Si no hay rango configurado para este parámetro, continuar
    if (!rango || typeof rango.min !== 'number' || typeof rango.max !== 'number') {
      return;
    }

    // 1. NUEVA VALIDACIÓN: Verifica si el valor actual YA está fuera de rango
    if (valorActual !== null && valorActual !== undefined && !isNaN(valorActual)) {
      if (valorActual > rango.max) {
        alertasUrgentes.push({
          tipo: 'Peligro',
          parametro: parametro.nombre,
          mensaje: `El nivel actual de ${parametro.nombre} (${valorActual}) supera el máximo seguro de ${rango.max}. Riesgo alto.`,
          accion: 'Tomar medida correctiva de inmediato.'
        });
        return;
      } else if (valorActual < rango.min) {
        alertasUrgentes.push({
          tipo: 'Peligro',
          parametro: parametro.nombre,
          mensaje: `El nivel actual de ${parametro.nombre} (${valorActual}) está por debajo del mínimo seguro de ${rango.min}.`,
          accion: 'Aditar suplemento de inmediato.'
        });
        return;
      }
    }

    // 2. VALIDACIÓN EXISTENTE: La que ya tenías para la proyección a futuro (cruces de línea)
    if (
      parametro.proyeccion3Dias !== null &&
      parametro.proyeccion3Dias !== undefined &&
      !isNaN(parametro.proyeccion3Dias) &&
      (parametro.proyeccion3Dias < rango.min || parametro.proyeccion3Dias > rango.max)
    ) {
      alertasUrgentes.push({
        tipo: 'Advertencia',
        parametro: parametro.nombre,
        mensaje: `A este ritmo, tu ${parametro.nombre} saldrá de la zona segura en los próximos días.`,
        accion: 'Medir mañana para confirmar tendencia.'
      });
    }
  });

  return alertasUrgentes;
}

/**
 * Evalúa las predicciones del sistema y dispara la notificación local si:
 * 1. Están habilitadas y autorizadas.
 * 2. La hora actual coincide o superó la hora elegida.
 * 3. No se ha notificado hoy todavía.
 * 4. Existen alertas urgentes (Peligro o Advertencia) o cambio de agua requerido.
 */
export async function checkAndTriggerScheduledNotification(predictions, rangosSeguros = RANGOS_SEGUROS_DEFAULT) {
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

  // Evaluar alertas urgentes usando evaluateScheduledReminder
  const alertas = evaluateScheduledReminder(predictions, rangosSeguros);
  const peligroAlert = alertas.find(a => a.tipo === 'Peligro');
  const advertenciaAlert = alertas.find(a => a.tipo === 'Advertencia');

  let shouldAlert = false;
  let alertTitle = '🌊 AquaPulse: Recordatorio de Medición';
  let alertBody = '';

  if (peligroAlert) {
    shouldAlert = true;
    alertTitle = `🚨 Peligro: ${peligroAlert.parametro} fuera de rango`;
    alertBody = `${peligroAlert.mensaje} ${peligroAlert.accion}`;
  } else if (advertenciaAlert) {
    shouldAlert = true;
    alertTitle = `⚠️ Advertencia: ${advertenciaAlert.parametro} en riesgo`;
    alertBody = `${advertenciaAlert.mensaje} ${advertenciaAlert.accion}`;
  } else if (predictions?.water_change_prediction?.urgency === 'immediate') {
    shouldAlert = true;
    alertTitle = '🚨 Cambio de Agua Requerido';
    alertBody = `Nitratos acumulados (${predictions.water_change_prediction.current_nitrate_ppm} ppm). Se recomienda cambio del ${predictions.water_change_prediction.suggested_percentage}%.`;
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
