import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';
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
  ArrowRight
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
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState(null);

  if (!isOpen) return null;

  const triggerHaptic = () => {
    if (typeof navigator !== 'undefined' && navigator.vibrate) {
      navigator.vibrate(15);
    }
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
      } else {
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
            {t('auth.headerTitle')}
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            {t('auth.headerSubtitle')}
          </p>
        </div>

        {/* Pestañas Iniciar Sesión / Crear Cuenta */}
        <div className="flex rounded-2xl bg-marine-950/80 p-1 mb-6 border border-marine-800">
          <button
            type="button"
            onClick={() => {
              triggerHaptic();
              setAuthModalTab('login');
              setError(null);
            }}
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
            onClick={() => {
              triggerHaptic();
              setAuthModalTab('register');
              setError(null);
            }}
            className={`flex-1 py-2.5 text-xs sm:text-sm font-black rounded-xl transition-all ${
              authModalTab === 'register'
                ? 'bg-gradient-to-r from-cyan-500 to-cyan-400 text-marine-950 shadow-md'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            {t('auth.registerTab')}
          </button>
        </div>

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

        {/* Formulario */}
        <form onSubmit={handleSubmit} className="space-y-4">
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

          <div>
            <label className="block text-xs font-extrabold uppercase text-slate-300 mb-1.5">
              {t('auth.passLabel')}
            </label>
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

          <button
            type="submit"
            disabled={loading}
            className="w-full min-h-[48px] rounded-2xl bg-gradient-to-r from-cyan-500 via-cyan-400 to-emerald-400 text-marine-950 font-black text-sm flex items-center justify-center gap-2 shadow-neon-cyan hover:brightness-110 active:scale-98 transition disabled:opacity-50"
          >
            {loading ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <>
                <span>{authModalTab === 'login' ? t('auth.btnLogin') : t('auth.btnRegister')}</span>
                <ArrowRight className="w-4 h-4 stroke-[3]" />
              </>
            )}
          </button>
        </form>

        {/* Separador */}
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

        {/* Badge de seguridad */}
        <div className="mt-4 flex items-center justify-center gap-1.5 text-slate-500 text-[11px]">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span>{t('auth.securityBadge')}</span>
        </div>
      </div>
    </div>
  );
}
