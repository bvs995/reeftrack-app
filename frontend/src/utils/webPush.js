import {
  fetchVapidPublicKey,
  registerPushSubscription,
  unregisterPushSubscription,
  updatePushPreferences,
  sendTestPush
} from '../api';

const PUSH_PREFS_KEY = 'aquapulse_push_preferences';

export function getLocalPushPreferences() {
  try {
    const raw = localStorage.getItem(PUSH_PREFS_KEY);
    if (raw) return JSON.parse(raw);
  } catch (e) {
    console.error('Error al leer preferencias push locales:', e);
  }
  return {
    notify_maintenance: true,
    notify_alerts: true
  };
}

export function saveLocalPushPreferences(prefs) {
  try {
    localStorage.setItem(PUSH_PREFS_KEY, JSON.stringify(prefs));
  } catch (e) {
    console.error('Error al guardar preferencias push locales:', e);
  }
}

export function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding)
    .replace(/-/g, '+')
    .replace(/_/g, '/');

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export function isPushSupported() {
  return (
    typeof window !== 'undefined' &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  );
}

export function isIosSafariNonStandalone() {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') return false;
  const ua = window.navigator.userAgent;
  const isIos = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const isStandalone = ('standalone' in window.navigator && window.navigator.standalone) || window.matchMedia('(display-mode: standalone)').matches;
  return isIos && !isStandalone;
}

export async function getPushSubscriptionState() {
  if (!isPushSupported()) {
    return {
      supported: false,
      permission: 'unsupported',
      isSubscribed: false,
      isIosNonStandalone: isIosSafariNonStandalone()
    };
  }

  const permission = Notification.permission; // 'default', 'granted', 'denied'
  let isSubscribed = false;

  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = await reg.pushManager.getSubscription();
    isSubscribed = !!sub;
  } catch (e) {
    console.warn('Error verificando suscripción existente en ServiceWorker:', e);
  }

  return {
    supported: true,
    permission,
    isSubscribed,
    isIosNonStandalone: isIosSafariNonStandalone()
  };
}

export async function subscribeToPushNotifications(options = {}) {
  if (!isPushSupported()) {
    throw new Error('Las notificaciones push no son soportadas en este navegador o dispositivo.');
  }

  // 1. Solicitar permiso explícito al usuario (obligatorio tras gesto de clic)
  const permission = await Notification.requestPermission();
  if (permission !== 'granted') {
    return { success: false, permission, reason: 'denied' };
  }

  // 2. Obtener clave pública VAPID desde el backend
  const { public_key } = await fetchVapidPublicKey();
  if (!public_key) {
    throw new Error('El servidor no tiene configurada una clave pública VAPID.');
  }

  // 3. Obtener registro de Service Worker y suscribir con PushManager
  const registration = await navigator.serviceWorker.ready;
  let subscription = await registration.pushManager.getSubscription();

  // Si ya existía una suscripción con otra clave o vencida, la renovamos
  if (subscription) {
    try {
      await subscription.unsubscribe();
    } catch (e) {
      console.warn('Aviso renovando suscripción previa:', e);
    }
  }

  const convertedKey = urlBase64ToUint8Array(public_key);
  subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: convertedKey
  });

  const rawKey = subscription.getKey ? subscription.getKey('p256dh') : null;
  const rawAuth = subscription.getKey ? subscription.getKey('auth') : null;

  const p256dh = rawKey ? btoa(String.fromCharCode.apply(null, new Uint8Array(rawKey))) : '';
  const auth = rawAuth ? btoa(String.fromCharCode.apply(null, new Uint8Array(rawAuth))) : '';

  const prefs = {
    notify_maintenance: options.notify_maintenance ?? true,
    notify_alerts: options.notify_alerts ?? true
  };

  // 4. Enviar suscripción a Supabase PostgreSQL vía FastAPI
  await registerPushSubscription({
    endpoint: subscription.endpoint,
    p256dh,
    auth,
    user_agent: navigator.userAgent.substring(0, 500),
    notify_maintenance: prefs.notify_maintenance,
    notify_alerts: prefs.notify_alerts
  });

  saveLocalPushPreferences(prefs);

  return { success: true, permission: 'granted', isSubscribed: true };
}

export async function unsubscribeFromPushNotifications() {
  if (!isPushSupported()) return { success: true };

  try {
    const registration = await navigator.serviceWorker.ready;
    const subscription = await registration.pushManager.getSubscription();
    if (subscription) {
      const endpoint = subscription.endpoint;
      await subscription.unsubscribe();
      try {
        await unregisterPushSubscription(endpoint);
      } catch (e) {
        console.warn('Aviso desregistrando suscripción del backend:', e);
      }
    }
  } catch (err) {
    console.error('Error al desuscribir push notifications:', err);
    throw err;
  }

  return { success: true, isSubscribed: false };
}

export async function savePreferencesOnServer(prefs) {
  saveLocalPushPreferences(prefs);
  return updatePushPreferences(prefs);
}

export async function sendTestNotificationToServer() {
  return sendTestPush();
}
