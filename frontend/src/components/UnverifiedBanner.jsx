import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { AlertTriangle, Mail, Send, CheckCircle2, AlertCircle, RefreshCw } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function UnverifiedBanner() {
  const { t } = useTranslation();
  const { user, isAuthenticated, resendVerification } = useAuth();

  const [isSending, setIsSending] = useState(false);
  const [feedback, setFeedback] = useState(null); // { type: 'success' | 'error', message: string } | null

  // Si no está autenticado o la cuenta ya está verificada, no mostrar nada
  if (!isAuthenticated || !user || user.email_verified) {
    return null;
  }

  const handleResend = async () => {
    if (!user?.email || isSending) return;
    setIsSending(true);
    setFeedback(null);

    try {
      const res = await resendVerification(user.email);
      setFeedback({
        type: 'success',
        message: res?.message || t('common.emailResentSuccess') || 'Correo de activación reenviado con éxito. Revisa tu bandeja de entrada.'
      });
    } catch (err) {
      setFeedback({
        type: 'error',
        message: err.message || t('common.emailResendError') || 'Error al reenviar el correo de verificación. Inténtalo más tarde.'
      });
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div
      role="alert"
      aria-live="polite"
      className="bg-gradient-to-r from-amber-950 via-amber-900 to-amber-950 border-b border-amber-500/50 text-amber-100 px-3 sm:px-6 py-2.5 sm:py-3 shadow-lg shrink-0 z-40 transition-all"
    >
      <div className="max-w-7xl mx-auto flex flex-col gap-2">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2.5">
          {/* Lado izquierdo: Icono y Mensaje principal */}
          <div className="flex items-center gap-2.5 sm:gap-3">
            <div className="w-8 h-8 rounded-xl bg-amber-500/20 border border-amber-500/40 text-amber-400 flex items-center justify-center shrink-0">
              <Mail className="w-4 h-4 animate-pulse" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-black text-xs sm:text-sm text-white tracking-wide">
                  {t('common.verifyEmailNotice') || 'Verifica tu correo para usar AquaReef'}
                </span>
                <span className="text-[10px] font-extrabold uppercase px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                  {t('common.unverifiedEmail') || 'Correo sin verificar'}
                </span>
              </div>
              <p className="text-[11px] sm:text-xs text-amber-200/80 truncate">
                Hemos enviado un enlace a <strong className="text-white font-mono">{user.email}</strong>. Confírmalo para activar telemetría y mediciones.
              </p>
            </div>
          </div>

          {/* Lado derecho: Botón de Reenviar Correo */}
          <div className="flex items-center gap-2 shrink-0 self-start sm:self-auto">
            <button
              type="button"
              onClick={handleResend}
              disabled={isSending}
              className="px-3.5 py-1.5 rounded-xl bg-gradient-to-r from-amber-500 to-amber-400 hover:from-amber-400 hover:to-amber-300 active:scale-95 text-marine-950 font-black text-xs shadow-md transition-all flex items-center gap-1.5 disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer"
            >
              {isSending ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>{t('common.resendingEmail') || 'Reenviando...'}</span>
                </>
              ) : (
                <>
                  <Send className="w-3.5 h-3.5" />
                  <span>{t('common.resendEmailBtn') || 'Reenviar correo'}</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Mensaje claro de Feedback (Éxito o Error) */}
        {feedback && (
          <div
            className={`p-2 sm:p-2.5 rounded-xl text-xs flex items-center gap-2 border transition-all ${
              feedback.type === 'success'
                ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-200'
                : 'bg-rose-500/20 border-rose-500/50 text-rose-200'
            }`}
          >
            {feedback.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            )}
            <span className="font-semibold">{feedback.message}</span>
          </div>
        )}
      </div>
    </div>
  );
}
