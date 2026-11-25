import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Mail, Send, AlertCircle, CheckCircle2, RefreshCw, Settings, LogOut, ShieldAlert } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function UnverifiedAccountView({ onOpenSettings }) {
  const { t } = useTranslation();
  const { user, resendVerification, logout } = useAuth();

  const [isSending, setIsSending] = useState(false);
  const [feedback, setFeedback] = useState(null);

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
    <div className="max-w-2xl mx-auto px-4 py-8 sm:py-12">
      <div className="bg-marine-900/90 border border-amber-500/30 rounded-3xl p-6 sm:p-10 shadow-2xl relative overflow-hidden backdrop-blur-sm">
        {/* Glow de fondo */}
        <div className="absolute -top-24 -right-24 w-64 h-64 bg-amber-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -left-24 w-64 h-64 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

        {/* Icono Principal */}
        <div className="flex justify-center mb-6">
          <div className="w-20 h-20 rounded-3xl bg-amber-500/10 border-2 border-amber-500/40 text-amber-400 flex items-center justify-center shadow-lg shadow-amber-500/10 relative">
            <Mail className="w-10 h-10 animate-pulse" />
            <div className="absolute -bottom-1 -right-1 w-6 h-6 rounded-full bg-marine-950 border-2 border-amber-400 flex items-center justify-center">
              <ShieldAlert className="w-3.5 h-3.5 text-amber-400" />
            </div>
          </div>
        </div>

        {/* Titular */}
        <h1 className="text-xl sm:text-2xl font-black text-white text-center tracking-tight mb-2">
          {t('common.verifyEmailNotice') || 'Verifica tu correo para usar AquaReef'}
        </h1>

        <p className="text-sm text-slate-300 text-center max-w-lg mx-auto mb-6">
          Para acceder a la telemetría, predicciones anti-colapso y registro de parámetros de tus acuarios, confirma el enlace que enviamos a:
        </p>

        {/* Correo y Estado */}
        <div className="max-w-md mx-auto mb-6 p-3 bg-marine-950/80 border border-marine-800 rounded-2xl flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 truncate">
            <Mail className="w-4 h-4 text-slate-400 shrink-0" />
            <span className="font-mono text-xs sm:text-sm text-slate-200 truncate">{user?.email}</span>
          </div>
          <span className="text-[10px] font-extrabold uppercase px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30 shrink-0">
            {t('common.unverifiedEmail') || 'Correo sin verificar'}
          </span>
        </div>

        {/* Feedback Alert */}
        {feedback && (
          <div
            className={`max-w-md mx-auto mb-6 p-3.5 rounded-2xl text-xs sm:text-sm flex items-center gap-2.5 border transition-all ${
              feedback.type === 'success'
                ? 'bg-emerald-500/10 border-emerald-500/40 text-emerald-300'
                : 'bg-rose-500/10 border-rose-500/40 text-rose-300'
            }`}
          >
            {feedback.type === 'success' ? (
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            ) : (
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            )}
            <span className="font-medium">{feedback.message}</span>
          </div>
        )}

        {/* Botón Reenviar Correo */}
        <div className="flex flex-col sm:flex-row gap-3 justify-center mb-8">
          <button
            type="button"
            onClick={handleResend}
            disabled={isSending}
            className="px-6 py-3 rounded-2xl bg-gradient-to-r from-amber-500 via-amber-400 to-amber-500 hover:brightness-110 active:scale-95 text-marine-950 font-black text-sm shadow-md transition flex items-center justify-center gap-2 disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer"
          >
            {isSending ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin" />
                <span>{t('common.resendingEmail') || 'Reenviando...'}</span>
              </>
            ) : (
              <>
                <Send className="w-4 h-4" />
                <span>{t('common.resendEmailBtn') || 'Reenviar correo'}</span>
              </>
            )}
          </button>

          {onOpenSettings && (
            <button
              type="button"
              onClick={onOpenSettings}
              className="px-5 py-3 rounded-2xl bg-marine-950 border border-marine-700 text-slate-300 hover:text-white hover:border-cyan-400 active:scale-95 font-bold text-sm transition flex items-center justify-center gap-2"
            >
              <Settings className="w-4 h-4 text-cyan-400" />
              <span>{t('nav.settingsTab') || 'Ajustes'}</span>
            </button>
          )}

          <button
            type="button"
            onClick={() => logout()}
            className="px-4 py-3 rounded-2xl bg-marine-950/60 border border-marine-800 text-slate-400 hover:text-rose-300 hover:border-rose-500/40 active:scale-95 font-bold text-sm transition flex items-center justify-center gap-1.5"
            title="Cerrar sesión"
          >
            <LogOut className="w-4 h-4" />
            <span className="sm:hidden">Cerrar sesión</span>
          </button>
        </div>

        {/* Guía en 3 Pasos */}
        <div className="border-t border-marine-800/80 pt-6">
          <p className="text-xs font-black uppercase text-slate-400 tracking-wider mb-4 text-center">
            ¿Cómo activar tu cuenta?
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-left">
            <div className="bg-marine-950/60 border border-marine-800/80 rounded-2xl p-3.5">
              <span className="text-cyan-400 font-black text-xs block mb-1">Paso 1</span>
              <p className="text-xs text-slate-300 font-medium">Revisa tu bandeja de entrada o spam.</p>
            </div>
            <div className="bg-marine-950/60 border border-marine-800/80 rounded-2xl p-3.5">
              <span className="text-cyan-400 font-black text-xs block mb-1">Paso 2</span>
              <p className="text-xs text-slate-300 font-medium">Abre el enlace &quot;Verificar mi correo&quot;.</p>
            </div>
            <div className="bg-marine-950/60 border border-marine-800/80 rounded-2xl p-3.5">
              <span className="text-cyan-400 font-black text-xs block mb-1">Paso 3</span>
              <p className="text-xs text-slate-300 font-medium">Tus telemetrías se activarán al instante.</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
