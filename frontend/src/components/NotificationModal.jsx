import React from 'react';
import { useTranslation } from 'react-i18next';
import { BellRing, X } from 'lucide-react';
import PushNotificationSettings from './PushNotificationSettings';

export default function NotificationModal({ isOpen, onClose }) {
  const { t, i18n } = useTranslation();

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg bg-marine-900 border-t sm:border border-marine-700/80 rounded-t-3xl sm:rounded-3xl shadow-2xl overflow-hidden max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 sm:p-5 border-b border-marine-800 bg-marine-950/80 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 flex items-center justify-center shadow-neon-cyan">
              <BellRing className="w-5 h-5" />
            </div>
            <div>
              <h3 className="font-black text-white text-base sm:text-lg">{t('push.sectionTitle')}</h3>
              <p className="text-xs text-slate-400">Web Push Notifications (VAPID)</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-10 h-10 rounded-xl bg-marine-800 text-slate-400 hover:text-white flex items-center justify-center transition active:scale-90"
            aria-label="Cerrar"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Contenido con Scroll */}
        <div className="p-4 sm:p-6 overflow-y-auto space-y-4">
          <PushNotificationSettings compact={false} />
        </div>

        {/* Footer */}
        <div className="p-4 sm:p-5 border-t border-marine-800 bg-marine-950/80 flex items-center justify-end safe-bottom shrink-0">
          <button
            type="button"
            onClick={onClose}
            className="btn-touch-primary w-full sm:w-auto"
          >
            {t('nav.close') || 'Cerrar'}
          </button>
        </div>
      </div>
    </div>
  );
}
