import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';
import {
  requestPasswordReset,
  confirmPasswordReset
} from '../api';
import {
  Waves,
  Lock,
  Mail,
  User,
  Sparkles,
  X,
  AlertCircle,
  CheckCircle,
  Loader2,
  ShieldCheck,
  ArrowRight,
  ArrowLeft,
  KeyRound,
  ExternalLink
} from 'lucide-react';

export default function AuthModal({ isOpen, onClose }) {
  const { t } = useTranslation();
  const {
    login,
    register,
    loginDemo,
    authModalTab,
    setAuthModalTab
  } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');

  // Estados específicos para recuperación y restablecimiento
  const [resetToken, setResetToken] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [devResetInfo, setDevResetInfo] = useState(null);

  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState(null);

  // Detectar token de restablecimiento en la URL al abrir o montar
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const tokenFromUrl = params.get('reset_token') || params.get('token');
      if (tokenFromUrl) {
        setResetToken(tokenFromUrl);
        setAuthModalTab('reset');
      }
    }
  }, [setAuthModalTab]);

  if (!isOpen) return null;

  const triggerHaptic = () => {
    if (typeof navigator !== 'undefined' && navigator.vibrate) {
      navigator.vibrate(15);
    }
  };

  const handleResetFormState = (newTab) => {
    triggerHaptic();
    setAuthModalTab(newTab);
    setError(null);
    setSuccessMsg(null);
    setDevResetInfo(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);
    setLoading(true);
    triggerHaptic();

    try {
      if (authModalTab === 'login') {
        if (!email.trim() || !password) {
          throw new Error(t('auth.errorEmpty'));
        }
        await login(email.trim(), password);
        if (onClose) onClose();
      } else if (authModalTab === 'register') {
        if (!email.trim() || !password) {
          throw new Error(t('auth.errorFields'));
        }
        if (password.length < 6) {
          throw new Error(t('auth.errorShortPass'));
        }
        await register(email.trim(), password, fullName.trim() || null);
        setSuccessMsg(t('auth.registerSuccess'));
        setTimeout(() => {
          if (onClose) onClose();
        }, 800);
      } else if (authModalTab === 'forgot') {
        if (!email.trim()) {
          throw new Error(t('auth.errorEmpty'));
        }
        const res = await requestPasswordReset(email.trim());
        setSuccessMsg(t('auth.resetLinkSent'));
        if (res.reset_url_dev || res.reset_token_dev) {
          setDevResetInfo({
            url: res.reset_url_dev,
            token: res.reset_token_dev
          });
        }
      } else if (authModalTab === 'reset') {
        if (!resetToken.trim()) {
          throw new Error('El token de restablecimiento es requerido.');
        }
        if (!newPassword || newPassword.length < 6) {
          throw new Error(t('auth.errorShortPass'));
        }
        if (newPassword !== confirmPassword) {
          throw new Error(t('auth.errorPassMismatch'));
        }
        await confirmPasswordReset(resetToken.trim(), newPassword);
        setSuccessMsg(t('auth.resetSuccess'));

        // Limpiar token de la URL sin recargar
        if (typeof window !== 'undefined' && window.history?.replaceState) {
          const url = new URL(window.location.href);
          url.searchParams.delete('reset_token');
          url.searchParams.delete('token');
          window.history.replaceState({}, '', url.pathname + (url.search || ''));
        }

        setTimeout(() => {
          handleResetFormState('login');
        }, 2000);
      }
    } catch (err) {
      setError(err.message || 'Error en la solicitud');
    } finally {
      setLoading(false);
    }
  };

  const handleDemoLogin = async () => {
    setError(null);
    setLoading(true);
    triggerHaptic();
    try {
      await loginDemo();
      if (onClose) onClose();
    } catch (err) {
      setError('Error al ingresar con la cuenta de demostración.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-marine-950/80 backdrop-blur-md animate-fadeIn">
      <div className="w-full max-w-md bg-marine-900 border border-marine-700/80 rounded-3xl p-6 sm:p-8 shadow-2xl relative overflow-hidden">
        {/* Glow de fondo náutico */}
        <div className="absolute -top-24 -right-24 w-52 h-52 bg-cyan-500/15 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -left-24 w-52 h-52 bg-emerald-500/15 rounded-full blur-3xl pointer-events-none" />

        {/* Botón cerrar */}
        <button
          onClick={() => {
            triggerHaptic();
            if (onClose) onClose();
          }}
          className="absolute top-5 right-5 text-slate-400 hover:text-white p-2 rounded-xl hover:bg-marine-800 transition"
          aria-label={t('common.close')}
        >
          <X className="w-5 h-5" />
        </button>

        {/* Logo & Header */}
        <div className="flex flex-col items-center text-center mb-6">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-cyan-600 via-cyan-400 to-emerald-400 flex items-center justify-center shadow-neon-cyan border border-white/20 mb-3">
            <Waves className="w-8 h-8 text-marine-950 stroke-[2.5]" />
          </div>
          <h2 className="text-xl sm:text-2xl font-black text-white tracking-tight">
            {authModalTab === 'forgot'
              ? t('auth.forgotTitle')
              : authModalTab === 'reset'
              ? t('auth.resetTitle')
              : t('auth.headerTitle')}
          </h2>
          <p className="text-xs text-slate-400 mt-1 max-w-xs">
            {authModalTab === 'forgot'
              ? t('auth.forgotSubtitle')
              : authModalTab === 'reset'
              ? t('auth.resetSubtitle')
              : t('auth.headerSubtitle')}
          </p>
        </div>

        {/* Pestañas Iniciar Sesión / Crear Cuenta (Ocultas en forgot o reset) */}
        {(authModalTab === 'login' || authModalTab === 'register') && (
          <div className="flex rounded-2xl bg-marine-950/80 p-1 mb-6 border border-marine-800">
            <button
              type="button"
              onClick={() => handleResetFormState('login')}
              className={`flex-1 py-2.5 text-xs sm:text-sm font-black rounded-xl transition-all ${
                authModalTab === 'login'
                  ? 'bg-gradient-to-r from-cyan-500 to-cyan-400 text-marine-950 shadow-md'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {t('auth.loginTab')}
            </button>
            <button
              type="button"
              onClick={() => handleResetFormState('register')}
              className={`flex-1 py-2.5 text-xs sm:text-sm font-black rounded-xl transition-all ${
                authModalTab === 'register'
                  ? 'bg-gradient-to-r from-cyan-500 to-cyan-400 text-marine-950 shadow-md'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {t('auth.registerTab')}
            </button>
          </div>
        )}

        {/* Notificaciones de Error / Éxito */}
        {error && (
          <div className="mb-4 p-3 rounded-2xl bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs font-semibold flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
            <span>{error}</span>
          </div>
        )}

        {successMsg && (
          <div className="mb-4 p-3 rounded-2xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs font-semibold flex items-center gap-2">
            <CheckCircle className="w-4 h-4 shrink-0 text-emerald-400" />
            <span>{successMsg}</span>
          </div>
        )}

        {/* Formulario Dinámico según Pestaña */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Nombre completo en Registro */}
          {authModalTab === 'register' && (
            <div>
              <label className="block text-xs font-extrabold uppercase text-slate-300 mb-1.5">
                {t('auth.nameLabel')}
              </label>
              <div className="relative">
                <User className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5 pointer-events-none" />
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder={t('auth.namePlaceholder')}
                  className="w-full bg-marine-950/90 border border-marine-700 rounded-2xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 focus:border-cyan-400 transition"
                />
              </div>
            </div>
          )}

          {/* Correo Electrónico (Login, Register, Forgot) */}
          {authModalTab !== 'reset' && (
            <div>
              <label className="block text-xs font-extrabold uppercase text-slate-300 mb-1.5">
                {t('auth.emailLabel')}
              </label>
              <div className="relative">
                <Mail className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5 pointer-events-none" />
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="acuarista@reef.com"
                  className="w-full bg-marine-950/90 border border-marine-700 rounded-2xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 focus:border-cyan-400 transition"
                />
              </div>
            </div>
          )}

          {/* Contraseña en Login y Register */}
          {(authModalTab === 'login' || authModalTab === 'register') && (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-extrabold uppercase text-slate-300">
                  {t('auth.passLabel')}
                </label>
                {authModalTab === 'login' && (
                  <button
                    type="button"
                    onClick={() => handleResetFormState('forgot')}
                    className="text-xs text-cyan-400 hover:text-cyan-300 font-bold hover:underline transition"
                  >
                    {t('auth.forgotPassword')}
                  </button>
                )}
              </div>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5 pointer-events-none" />
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full bg-marine-950/90 border border-marine-700 rounded-2xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 focus:border-cyan-400 transition"
                />
              </div>
              {authModalTab === 'register' && (
                <p className="text-[11px] text-slate-500 mt-1">{t('auth.passHint')}</p>
              )}
            </div>
          )}

          {/* Campos para Restablecimiento de Contraseña (Reset Mode) */}
          {authModalTab === 'reset' && (
            <>
              <div>
                <label className="block text-xs font-extrabold uppercase text-slate-300 mb-1.5">
                  {t('auth.newPassLabel')}
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5 pointer-events-none" />
                  <input
                    type="password"
                    required
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full bg-marine-950/90 border border-marine-700 rounded-2xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 focus:border-cyan-400 transition"
                  />
                </div>
                <p className="text-[11px] text-slate-500 mt-1">{t('auth.passHint')}</p>
              </div>

              <div>
                <label className="block text-xs font-extrabold uppercase text-slate-300 mb-1.5">
                  {t('auth.confirmPassLabel')}
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5 pointer-events-none" />
                  <input
                    type="password"
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="••••••••"
                    className="w-full bg-marine-950/90 border border-marine-700 rounded-2xl pl-10 pr-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 focus:border-cyan-400 transition"
                  />
                </div>
              </div>
            </>
          )}

          {/* Tarjeta de Prueba Local / Dev (Sin SMTP) */}
          {devResetInfo && authModalTab === 'forgot' && (
            <div className="p-4 rounded-2xl bg-cyan-950/60 border border-cyan-500/40 text-cyan-200 text-xs space-y-2.5 animate-fadeIn">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-cyan-400 shrink-0" />
                <span className="font-extrabold">{t('auth.devLinkNotice')}</span>
              </div>
              <p className="text-[11px] text-slate-400">
                El enlace se ha emitido en la consola de FastAPI. Para probar el flujo inmediatamente:
              </p>
              <button
                type="button"
                onClick={() => {
                  triggerHaptic();
                  setResetToken(devResetInfo.token);
                  setAuthModalTab('reset');
                  setError(null);
                  setSuccessMsg(null);
                }}
                className="w-full py-2.5 px-3 rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-400 text-marine-950 font-black text-xs flex items-center justify-center gap-1.5 shadow-neon-cyan hover:brightness-110 active:scale-95 transition"
              >
                <KeyRound className="w-3.5 h-3.5 stroke-[2.5]" />
                <span>{t('auth.devLinkAction')}</span>
              </button>
            </div>
          )}

          {/* Botón Principal de Envío */}
          <button
            type="submit"
            disabled={loading}
            className="w-full min-h-[48px] rounded-2xl bg-gradient-to-r from-cyan-500 via-cyan-400 to-emerald-400 text-marine-950 font-black text-sm flex items-center justify-center gap-2 shadow-neon-cyan hover:brightness-110 active:scale-98 transition disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <>
                <span>
                  {authModalTab === 'login'
                    ? t('auth.btnLogin')
                    : authModalTab === 'register'
                    ? t('auth.btnRegister')
                    : authModalTab === 'forgot'
                    ? t('auth.btnSendReset')
                    : t('auth.btnResetPassword')}
                </span>
                <ArrowRight className="w-4 h-4 stroke-[3]" />
              </>
            )}
          </button>
        </form>

        {/* Botón Volver a Iniciar Sesión en Vistas Secundarias */}
        {(authModalTab === 'forgot' || authModalTab === 'reset') && (
          <div className="mt-4 text-center">
            <button
              type="button"
              onClick={() => handleResetFormState('login')}
              className="text-xs text-slate-400 hover:text-white font-bold flex items-center justify-center gap-1.5 mx-auto transition"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>{t('auth.backToLogin')}</span>
            </button>
          </div>
        )}

        {/* Separador y Demo Login solo en Login/Register */}
        {(authModalTab === 'login' || authModalTab === 'register') && (
          <>
            <div className="relative my-5">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-marine-800" />
              </div>
              <div className="relative flex justify-center text-xs">
                <span className="bg-marine-900 px-3 text-slate-400 font-bold uppercase text-[10px] tracking-wider">
                  {t('auth.orImmediate')}
                </span>
              </div>
            </div>

            {/* Botón Acceso Rápido Demo 1-Click */}
            <button
              type="button"
              onClick={handleDemoLogin}
              disabled={loading}
              className="w-full min-h-[44px] rounded-2xl bg-marine-950/90 border border-cyan-500/40 hover:border-cyan-400 text-cyan-300 font-bold text-xs sm:text-sm flex items-center justify-center gap-2 hover:bg-cyan-500/10 active:scale-98 transition"
            >
              <Sparkles className="w-4 h-4 text-cyan-400" />
              <span>{t('auth.btnDemo')}</span>
            </button>
          </>
        )}

        {/* Badge de seguridad */}
        <div className="mt-4 flex items-center justify-center gap-1.5 text-slate-500 text-[11px]">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span>{t('auth.securityBadge')}</span>
        </div>
      </div>
    </div>
  );
}
