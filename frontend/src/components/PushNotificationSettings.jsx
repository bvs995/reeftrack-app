import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Bell,
  BellRing,
  BellOff,
  AlertTriangle,
  Wrench,
  Send,
  CheckCircle2,
  AlertCircle,
  Smartphone,
  Info,
  Loader2
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import {
  getPushSubscriptionState,
  subscribeToPushNotifications,
  unsubscribeFromPushNotifications,
  getLocalPushPreferences,
  savePreferencesOnServer,
  sendTestNotificationToServer
} from '../utils/webPush';

export default function PushNotificationSettings({ compact = false }) {
  const { t, i18n } = useTranslation();
  const { isAuthenticated, openAuthModal } = useAuth();

  const [pushState, setPushState] = useState({
    supported: true,
    permission: 'default',
    isSubscribed: false,
    isIosNonStandalone: false
  });
  const [preferences, setPreferences] = useState(getLocalPushPreferences());
  const [loading, setLoading] = useState(false);
  const [testSending, setTestSending] = useState(false);
  const [feedback, setFeedback] = useState(null);

  const triggerHaptic = () => {
    if (typeof navigator !== 'undefined' && navigator.vibrate) {
      navigator.vibrate(15);
    }
  };

  const refreshState = async () => {
    try {
      const state = await getPushSubscriptionState();
      setPushState(state);
      setPreferences(getLocalPushPreferences());
    } catch (e) {
      console.error('Error refrescando estado de push:', e);
    }
  };

  useEffect(() => {
    refreshState();
  }, [isAuthenticated]);

  const handleToggleSubscription = async () => {
    triggerHaptic();
    setFeedback(null);

    if (!isAuthenticated) {
      setFeedback({
        type: 'info',
        text: t('settings.sessionRequiredDesc')
      });
      if (openAuthModal) openAuthModal('login');
      return;
    }

    setLoading(true);
    try {
      if (pushState.isSubscribed) {
        await unsubscribeFromPushNotifications();
        await refreshState();
        setFeedback({
          type: 'success',
          text: t('push.statusInactive')
        });
      } else {
        const res = await subscribeToPushNotifications(preferences);
        await refreshState();
        if (res.success) {
          setFeedback({
            type: 'success',
            text: t('push.statusActive')
          });
        } else if (res.reason === 'denied') {
          setFeedback({
            type: 'error',
            text: t('push.permissionDenied')
          });
        }
      }
    } catch (err) {
      console.error('Error al cambiar suscripción push:', err);
      setFeedback({
        type: 'error',
        text: err.message || 'Error al procesar la suscripción push.'
      });
    } finally {
      setLoading(false);
    }
  };

  const handleTogglePreference = async (key) => {
    triggerHaptic();
    const updated = {
      ...preferences,
      [key]: !preferences[key]
    };
    setPreferences(updated);

    if (pushState.isSubscribed && isAuthenticated) {
      try {
        await savePreferencesOnServer(updated);
      } catch (err) {
        console.warn('Aviso sincronizando preferencias en servidor:', err);
      }
    }
  };

  const handleSendTest = async () => {
    triggerHaptic();
    setFeedback(null);

    if (!isAuthenticated) {
      if (openAuthModal) openAuthModal('login');
      return;
    }

    if (!pushState.isSubscribed) {
      setFeedback({
        type: 'error',
        text: 'Primero debes activar las notificaciones en este dispositivo.'
      });
      return;
    }

    setTestSending(true);
    try {
      const res = await sendTestNotificationToServer();
      if (res.status === 'success') {
        setFeedback({
          type: 'success',
          text: t('push.testSuccess')
        });
      } else {
        setFeedback({
          type: 'info',
          text: res.message || 'La notificación fue emitida por el servidor.'
        });
      }
    } catch (err) {
      console.error('Error enviando notificación de prueba:', err);
      setFeedback({
        type: 'error',
        text: err.message || 'Error al enviar notificación de prueba.'
      });
    } finally {
      setTestSending(false);
    }
  };

  // Determinar badge visual de estado
  let statusBadge = {
    text: t('push.statusInactive'),
    classes: 'bg-slate-500/20 text-slate-300 border-slate-500/40'
  };

  if (!pushState.supported) {
    statusBadge = {
      text: t('push.statusUnsupported'),
      classes: 'bg-amber-500/20 text-amber-300 border-amber-500/40'
    };
  } else if (pushState.permission === 'denied') {
    statusBadge = {
      text: t('push.statusBlocked'),
      classes: 'bg-rose-500/20 text-rose-300 border-rose-500/40'
    };
  } else if (pushState.isSubscribed) {
    statusBadge = {
      text: t('push.statusActive'),
      classes: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-neon-emerald'
    };
  }

  return (
    <div className="space-y-4">
      {/* Encabezado y Estado */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-marine-800">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 flex items-center justify-center shrink-0 shadow-neon-cyan">
            {pushState.isSubscribed ? <BellRing className="w-5 h-5" /> : <Bell className="w-5 h-5" />}
          </div>
          <div>
            <h3 className="text-base font-black text-white">{t('push.sectionTitle')}</h3>
            {!compact && (
              <p className="text-xs text-slate-400">
                {t('push.sectionSubtitle')}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          <span className={`text-[11px] font-black uppercase px-3 py-1 rounded-full border ${statusBadge.classes}`}>
            {statusBadge.text}
          </span>
        </div>
      </div>

      {/* Banner de Feedback */}
      {feedback && (
        <div
          className={`p-3.5 rounded-2xl border text-xs font-semibold flex items-center gap-2.5 animate-in fade-in ${
            feedback.type === 'success'
              ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
              : feedback.type === 'error'
              ? 'bg-rose-500/15 border-rose-500/40 text-rose-300'
              : 'bg-cyan-500/15 border-cyan-500/40 text-cyan-300'
          }`}
        >
          {feedback.type === 'success' ? (
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
          ) : feedback.type === 'error' ? (
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
          ) : (
            <Info className="w-4 h-4 shrink-0 text-cyan-400" />
          )}
          <span>{feedback.text}</span>
        </div>
      )}

      {/* Nota específica para iOS Safari sin instalar como PWA */}
      {pushState.isIosNonStandalone && (
        <div className="p-3.5 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-200 text-xs space-y-1">
          <div className="flex items-center gap-2 font-black text-amber-300">
            <Smartphone className="w-4 h-4 shrink-0" />
            <span>{t('push.iosNoticeTitle')}</span>
          </div>
          <p className="text-[11px] text-amber-200/90 leading-relaxed">
            {t('push.iosNoticeDesc')}
          </p>
        </div>
      )}

      {/* Botón Principal: Activar / Desactivar */}
      {pushState.supported && pushState.permission !== 'denied' && (
        <button
          type="button"
          onClick={handleToggleSubscription}
          disabled={loading}
          className={`w-full min-h-[46px] rounded-2xl font-black text-xs sm:text-sm flex items-center justify-center gap-2 transition active:scale-95 shadow-md ${
            pushState.isSubscribed
              ? 'bg-marine-950/80 hover:bg-rose-500/10 text-rose-300 border border-rose-500/30'
              : 'bg-gradient-to-r from-cyan-500 to-blue-600 hover:brightness-110 text-marine-950 font-black shadow-neon-cyan'
          }`}
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Procesando...</span>
            </>
          ) : pushState.isSubscribed ? (
            <>
              <BellOff className="w-4 h-4" />
              <span>{t('push.btnDisable')}</span>
            </>
          ) : (
            <>
              <Bell className="w-4 h-4 stroke-[2.5]" />
              <span>{t('push.btnEnable')}</span>
            </>
          )}
        </button>
      )}

      {/* Mensaje si el permiso está denegado */}
      {pushState.permission === 'denied' && (
        <div className="p-3 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs font-medium">
          {t('push.blockedHint')}
        </div>
      )}

      {/* Interruptores de Preferencias */}
      <div className="space-y-3 pt-2">
        {/* Switch: Recordatorios de Mantenimiento */}
        <div className="flex items-center justify-between p-3.5 rounded-2xl bg-marine-950/70 border border-marine-800">
          <div className="space-y-0.5 pr-4">
            <div className="flex items-center gap-2">
              <Wrench className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
              <span className="text-xs sm:text-sm font-bold text-white">
                {t('push.maintenanceLabel')}
              </span>
            </div>
            <p className="text-[11px] text-slate-400 leading-snug">
              {t('push.maintenanceDesc')}
            </p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer shrink-0">
            <input
              type="checkbox"
              checked={preferences.notify_maintenance}
              onChange={() => handleTogglePreference('notify_maintenance')}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-marine-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-cyan-500 shadow-inner"></div>
          </label>
        </div>

        {/* Switch: Alertas Críticas de Parámetros */}
        <div className="flex items-center justify-between p-3.5 rounded-2xl bg-marine-950/70 border border-marine-800">
          <div className="space-y-0.5 pr-4">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
              <span className="text-xs sm:text-sm font-bold text-white">
                {t('push.alertsLabel')}
              </span>
            </div>
            <p className="text-[11px] text-slate-400 leading-snug">
              {t('push.alertsDesc')}
            </p>
          </div>
          <label className="relative inline-flex items-center cursor-pointer shrink-0">
            <input
              type="checkbox"
              checked={preferences.notify_alerts}
              onChange={() => handleTogglePreference('notify_alerts')}
              className="sr-only peer"
            />
            <div className="w-11 h-6 bg-marine-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-cyan-500 shadow-inner"></div>
          </label>
        </div>
      </div>

      {/* Botón: Enviar Notificación de Prueba */}
      {pushState.isSubscribed && (
        <button
          type="button"
          onClick={handleSendTest}
          disabled={testSending}
          className="w-full min-h-[42px] px-4 rounded-xl bg-marine-950 border border-cyan-500/30 hover:border-cyan-500/60 text-cyan-300 font-bold text-xs flex items-center justify-center gap-2 transition active:scale-95 hover:bg-cyan-500/10"
        >
          {testSending ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>{t('push.testSending')}</span>
            </>
          ) : (
            <>
              <Send className="w-3.5 h-3.5" />
              <span>{t('push.btnSendTest')}</span>
            </>
          )}
        </button>
      )}
    </div>
  );
}
