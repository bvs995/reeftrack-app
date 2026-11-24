import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Mail,
  ArrowRight,
  X,
  ShieldCheck,
  Send
} from 'lucide-react';

export default function EmailVerificationModal({
  isOpen,
  status, // 'verifying' | 'success' | 'error'
  errorMessage,
  defaultEmail = '',
  onClose,
  onResend,
  onSuccessContinue
}) {
  const { t } = useTranslation();
  const [resendEmail, setResendEmail] = useState(defaultEmail);
  const [resending, setResending] = useState(false);
  const [resendSuccess, setResendSuccess] = useState(null);
  const [resendError, setResendError] = useState(null);

  if (!isOpen) return null;

  const handleResendSubmit = async (e) => {
    e.preventDefault();
    if (!resendEmail || !resendEmail.trim()) {
      setResendError('Por favor ingresa tu correo electrónico.');
      return;
    }
    setResending(true);
    setResendError(null);
    setResendSuccess(null);
    try {
      if (onResend) {
        const res = await onResend(resendEmail.trim());
        setResendSuccess(res?.message || 'Si la cuenta existe, recibirás un nuevo enlace de activación.');
      }
    } catch (err) {
      setResendError(err.message || 'No se pudo reenviar el correo. Intenta nuevamente.');
    } finally {
      setResending(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-marine-950/80 backdrop-blur-md animate-fadeIn">
      <div className="relative w-full max-w-md p-6 sm:p-8 rounded-3xl bg-marine-900 border border-marine-800 shadow-2xl overflow-hidden">
        
        {/* Botón de cierre superior (disponible en éxito o error) */}
        {status !== 'verifying' && (
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-2 rounded-xl text-slate-400 hover:text-white hover:bg-marine-800/60 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        )}

        {/* 1. ESTADO: VERIFICANDO */}
        {status === 'verifying' && (
          <div className="text-center py-6 space-y-4">
            <div className="relative inline-flex items-center justify-center">
              <div className="w-16 h-16 rounded-2xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400">
                <Loader2 className="w-8 h-8 animate-spin" />
              </div>
            </div>
            <div>
              <h3 className="text-xl font-bold text-white tracking-wide">
                Verificando tu cuenta...
              </h3>
              <p className="mt-2 text-sm text-slate-400 leading-relaxed max-w-xs mx-auto">
                Confirmando tu dirección de correo electrónico con AquaPulse Cloud. Por favor espera un momento.
              </p>
            </div>
          </div>
        )}

        {/* 2. ESTADO: CUENTA VERIFICADA */}
        {status === 'success' && (
          <div className="text-center py-4 space-y-5 animate-scaleUp">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 shadow-[0_0_24px_rgba(16,185,129,0.2)]">
              <CheckCircle2 className="w-9 h-9" />
            </div>

            <div>
              <h3 className="text-2xl font-bold text-white tracking-tight">
                ¡Cuenta verificada!
              </h3>
              <p className="mt-2 text-sm text-slate-300 leading-relaxed">
                Tu correo electrónico ha sido confirmado exitosamente. Tu cuenta está completamente activa y lista para registrar mediciones.
              </p>
            </div>

            <div className="p-3.5 rounded-2xl bg-marine-950/80 border border-marine-800/80 text-xs text-slate-400 flex items-center gap-2.5 text-left">
              <ShieldCheck className="w-5 h-5 text-cyan-400 shrink-0" />
              <span>Ya puedes guardar parámetros, registrar mantenimientos y acceder a diagnósticos con IA.</span>
            </div>

            <button
              onClick={() => {
                if (onSuccessContinue) onSuccessContinue();
                onClose();
              }}
              className="w-full py-3.5 px-4 rounded-xl font-bold text-sm bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white shadow-lg shadow-cyan-500/20 flex items-center justify-center gap-2 transition-all active:scale-[0.98]"
            >
              <span>Comenzar a usar AquaPulse</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        )}

        {/* 3. ESTADO: ENLACE INVÁLIDO O EXPIRADO */}
        {status === 'error' && (
          <div className="py-3 space-y-5 animate-scaleUp">
            <div className="text-center space-y-2">
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-400">
                <AlertTriangle className="w-7 h-7" />
              </div>
              <h3 className="text-xl font-bold text-white">
                Enlace inválido o expirado
              </h3>
              <p className="text-xs sm:text-sm text-slate-300 leading-relaxed">
                {errorMessage || 'El enlace de verificación no es válido, ha caducado (duración 24h) o ya fue utilizado previamente.'}
              </p>
            </div>

            {/* Formulario para reenviar correo de verificación */}
            <form onSubmit={handleResendSubmit} className="p-4 rounded-2xl bg-marine-950/90 border border-marine-800 space-y-3">
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-300">
                <Mail className="w-4 h-4 text-cyan-400" />
                <span>¿Necesitas un nuevo enlace de activación?</span>
              </div>

              <div>
                <input
                  type="email"
                  value={resendEmail}
                  onChange={(e) => setResendEmail(e.target.value)}
                  placeholder="tu@correo.com"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-marine-900 border border-marine-700 text-white text-sm placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-colors"
                />
              </div>

              {resendError && (
                <p className="text-xs text-rose-400 flex items-center gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                  <span>{resendError}</span>
                </p>
              )}

              {resendSuccess && (
                <p className="text-xs text-emerald-400 flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                  <span>{resendSuccess}</span>
                </p>
              )}

              <button
                type="submit"
                disabled={resending || !resendEmail.trim()}
                className="w-full py-2.5 px-4 rounded-xl font-bold text-xs bg-marine-800 hover:bg-marine-700 text-cyan-300 hover:text-cyan-200 border border-marine-700 flex items-center justify-center gap-2 transition-all disabled:opacity-50"
              >
                {resending ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>Enviando enlace...</span>
                  </>
                ) : (
                  <>
                    <Send className="w-3.5 h-3.5" />
                    <span>Reenviar correo de verificación</span>
                  </>
                )}
              </button>
            </form>

            <button
              onClick={onClose}
              className="w-full py-2.5 text-center text-xs text-slate-400 hover:text-slate-200 transition-colors"
            >
              Cerrar
            </button>
          </div>
        )}

      </div>
    </div>
  );
}
