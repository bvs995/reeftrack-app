import React, { useState, useEffect } from 'react';
import {
  Bell,
  BellRing,
  Clock,
  Check,
  X,
  AlertTriangle,
  Sparkles,
  ShieldAlert,
  Send
} from 'lucide-react';
import {
  getNotificationSettings,
  saveNotificationSettings,
  requestNotificationPermission,
  getPermissionState,
  sendLocalNotification
} from '../utils/notifications';

export default function NotificationModal({ isOpen, onClose }) {
  const [settings, setSettings] = useState(getNotificationSettings());
  const [permission, setPermission] = useState(getPermissionState());
  const [testSent, setTestSent] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);

  useEffect(() => {
    if (isOpen) {
      setSettings(getNotificationSettings());
      setPermission(getPermissionState());
      setTestSent(false);
      setErrorMessage(null);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleRequestPermission = async () => {
    try {
      const result = await requestNotificationPermission();
      setPermission(result);
      if (result === 'granted') {
        const updated = { ...settings, enabled: true };
        setSettings(updated);
        saveNotificationSettings(updated);
      } else if (result === 'denied') {
        setErrorMessage('El permiso fue denegado en el navegador. Habilítalo en la configuración de permisos del sitio.');
      }
    } catch (err) {
      setErrorMessage(err.message || 'Error al solicitar permisos');
    }
  };

  const handleToggleEnable = (e) => {
    const isChecked = e.target.checked;
    if (isChecked && permission !== 'granted') {
      handleRequestPermission();
      return;
    }
    const updated = { ...settings, enabled: isChecked };
    setSettings(updated);
    saveNotificationSettings(updated);
  };

  const handleTimeChange = (e) => {
    const updated = { ...settings, reminderTime: e.target.value };
    setSettings(updated);
    saveNotificationSettings(updated);
  };

  const handleSendTest = async () => {
    setErrorMessage(null);
    if (permission !== 'granted') {
      await handleRequestPermission();
    }
    const success = await sendLocalNotification('🌊 AquaPulse: Notificación de Prueba', {
      body: '¡Sistema de alertas activo! Te notificaremos a las ' + settings.reminderTime + ' si tu dKH o nitratos requieren atención.',
      icon: '/favicon.svg'
    });

    if (success) {
      setTestSent(true);
      setTimeout(() => setTestSent(false), 3000);
    } else {
      setErrorMessage('No se pudo enviar la notificación. Verifica que los permisos del navegador estén activos.');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-md bg-marine-900 border-t sm:border border-marine-700/80 rounded-t-3xl sm:rounded-3xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 sm:p-5 border-b border-marine-800 bg-marine-950/80">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 flex items-center justify-center shadow-neon-cyan">
              <BellRing className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-black text-white text-base sm:text-lg">Recordatorios y Notificaciones</h3>
              <p className="text-xs text-slate-400">Web Notifications API</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-10 h-10 rounded-xl bg-marine-800 text-slate-400 hover:text-white flex items-center justify-center transition active:scale-90"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {errorMessage && (
          <div className="mx-4 mt-3 p-3.5 rounded-2xl bg-coral-500/15 border border-coral-500/40 text-coral-300 text-xs font-semibold">
            {errorMessage}
          </div>
        )}

        {/* Contenido */}
        <div className="p-4 sm:p-6 space-y-5">
          {/* Estado de Permiso */}
          <div className="flex items-center justify-between p-3.5 rounded-2xl bg-marine-950 border border-marine-800">
            <div className="flex items-center gap-2.5">
              <span className="text-xs font-bold text-slate-300">Permiso del Navegador:</span>
            </div>
            <span
              className={`text-[11px] font-black uppercase px-2.5 py-1 rounded-full border ${
                permission === 'granted'
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-neon-emerald'
                  : permission === 'denied'
                  ? 'bg-coral-500/20 text-coral-300 border-coral-500/40'
                  : 'bg-amber-500/20 text-amber-300 border-amber-500/40'
              }`}
            >
              {permission === 'granted' ? 'Permitido' : permission === 'denied' ? 'Bloqueado' : 'Pendiente'}
            </span>
          </div>

          {/* Toggle Activar Notificaciones */}
          <div className="flex items-center justify-between p-4 rounded-2xl bg-marine-950/90 border border-marine-800">
            <div className="space-y-0.5">
              <span className="text-sm font-extrabold text-white block">
                Alertas Diarias Predictivas
              </span>
              <p className="text-xs text-slate-400">
                Avisa si el motor estima que tu dKH o nitratos requieren medición hoy.
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={settings.enabled && permission === 'granted'}
                onChange={handleToggleEnable}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-marine-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-cyan-500 shadow-inner"></div>
            </label>
          </div>

          {/* Selector de Hora Táctil Grande */}
          <div className="glass-panel p-4 rounded-2xl border border-marine-800 space-y-2">
            <label className="block text-xs font-black uppercase tracking-wider text-slate-300 flex items-center gap-2">
              <Clock className="w-4 h-4 text-cyan-400" />
              Hora del Recordatorio
            </label>
            <input
              type="time"
              value={settings.reminderTime}
              onChange={handleTimeChange}
              className="w-full min-h-[48px] bg-marine-950 border border-marine-700 focus:border-cyan-400 rounded-xl px-4 text-xl font-black text-cyan-300 focus:outline-none shadow-inner"
            />
            <p className="text-[11px] text-slate-400 font-medium">
              Te alertaremos a esta hora si tu acuario requiere atención ese día.
            </p>
          </div>

          {/* Botón de Prueba */}
          <button
            type="button"
            onClick={handleSendTest}
            className="w-full min-h-[46px] btn-touch-secondary text-xs sm:text-sm font-black flex items-center justify-center gap-2 text-cyan-300 hover:text-cyan-200 border-cyan-500/30"
          >
            <Send className="w-4 h-4" />
            <span>{testSent ? '¡Notificación de Prueba Enviada!' : 'Probar Notificación Ahora'}</span>
          </button>
        </div>

        {/* Footer */}
        <div className="p-4 sm:p-5 border-t border-marine-800 bg-marine-950/80 flex items-center justify-end safe-bottom">
          <button
            type="button"
            onClick={onClose}
            className="btn-touch-primary w-full sm:w-auto"
          >
            Guardar Configuración
          </button>
        </div>
      </div>
    </div>
  );
}
