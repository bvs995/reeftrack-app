import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';
import {
  User,
  Mail,
  Scale,
  Crown,
  Sparkles,
  Lock,
  LogOut,
  Check,
  Save,
  AlertCircle,
  Database,
  ShieldCheck,
  CheckCircle2,
  Calendar,
  Layers
} from 'lucide-react';

export default function SettingsView({ onOpenAuthModal, onOpenAdmin }) {
  const { t, i18n } = useTranslation();
  const {
    user,
    isAuthenticated,
    unitPreference,
    subscriptionTier,
    updateProfile,
    logout,
    openAuthModal
  } = useAuth();

  const [fullName, setFullName] = useState(user?.full_name || '');
  const [selectedUnits, setSelectedUnits] = useState(unitPreference || 'liters');
  const [saving, setSaving] = useState(false);
  const [statusMessage, setStatusMessage] = useState(null);

  const triggerHaptic = () => {
    if (typeof navigator !== 'undefined' && navigator.vibrate) {
      navigator.vibrate(15);
    }
  };

  const handleSaveProfile = async (e) => {
    if (e) e.preventDefault();
    triggerHaptic();
    setSaving(true);
    setStatusMessage(null);
    try {
      await updateProfile({
        full_name: fullName.trim() || null,
        unit_preference: selectedUnits
      });
      setStatusMessage({ type: 'success', text: t('settings.savedSuccess') });
      setTimeout(() => setStatusMessage(null), 3500);
    } catch (err) {
      setStatusMessage({ type: 'error', text: err.message || t('settings.saveError') });
    } finally {
      setSaving(false);
    }
  };

  const handleUnitChange = async (unit) => {
    triggerHaptic();
    setSelectedUnits(unit);
    setSaving(true);
    setStatusMessage(null);
    try {
      await updateProfile({
        full_name: fullName.trim() || undefined,
        unit_preference: unit
      });
      setStatusMessage({
        type: 'success',
        text: t('settings.unitUpdated', {
          unit: unit === 'liters' ? t('settings.metricUnit') : t('settings.imperialUnit')
        })
      });
      setTimeout(() => setStatusMessage(null), 3000);
    } catch (err) {
      setStatusMessage({ type: 'error', text: t('settings.saveError') });
    } finally {
      setSaving(false);
    }
  };

  const handleLogoutClick = () => {
    triggerHaptic();
    if (window.confirm(t('settings.confirmLogout'))) {
      logout();
    }
  };

  // Si no está autenticado, mostrar tarjeta de bienvenida para registrarse o ingresar
  if (!isAuthenticated) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8 pb-28 sm:pb-12 animate-fadeIn">
        <div className="bg-marine-900/90 border border-marine-800 rounded-3xl p-6 sm:p-10 text-center shadow-2xl relative overflow-hidden">
          <div className="w-16 h-16 rounded-3xl bg-cyan-500/20 text-cyan-300 flex items-center justify-center mx-auto mb-4 border border-cyan-400/40">
            <Lock className="w-8 h-8" />
          </div>
          <h2 className="text-2xl font-black text-white mb-2">{t('settings.sessionRequiredTitle')}</h2>
          <p className="text-sm text-slate-400 max-w-md mx-auto mb-6">
            {t('settings.sessionRequiredDesc')}
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <button
              onClick={() => openAuthModal('login')}
              className="px-6 py-3 rounded-2xl bg-gradient-to-r from-cyan-500 to-cyan-400 text-marine-950 font-black text-sm shadow-neon-cyan hover:brightness-110 active:scale-95 transition"
            >
              {t('app.loginBtn')}
            </button>
            <button
              onClick={() => openAuthModal('register')}
              className="px-6 py-3 rounded-2xl bg-marine-950 border border-marine-700 text-slate-200 font-bold text-sm hover:border-cyan-400 active:scale-95 transition"
            >
              {t('app.registerBtn')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const initials = (user?.full_name || user?.email || 'A')
    .split(' ')
    .map((n) => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  const formattedDate = user?.created_at
    ? new Date(user.created_at).toLocaleDateString(i18n.language || 'es', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      })
    : t('common.active');

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 sm:py-8 pb-28 sm:pb-12 space-y-6 sm:space-y-8 animate-fadeIn">
      {/* Encabezado */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight flex items-center gap-3">
          <span>{t('settings.title')}</span>
          <span className="text-xs uppercase font-black px-2.5 py-1 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-400/40">
            {t('settings.badge')}
          </span>
        </h1>
        <p className="text-xs sm:text-sm text-slate-400 mt-1">
          {t('settings.subtitle')}
        </p>
      </div>

      {/* Banner de Estado */}
      {statusMessage && (
        <div
          className={`p-4 rounded-2xl text-xs sm:text-sm font-semibold flex items-center gap-3 border animate-fadeIn ${
            statusMessage.type === 'success'
              ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-300'
              : 'bg-rose-500/15 border-rose-500/30 text-rose-300'
          }`}
        >
          {statusMessage.type === 'success' ? (
            <CheckCircle2 className="w-5 h-5 shrink-0 text-emerald-400" />
          ) : (
            <AlertCircle className="w-5 h-5 shrink-0 text-rose-400" />
          )}
          <span>{statusMessage.text}</span>
        </div>
      )}

      {/* 1. SECCIÓN DE PERFIL */}
      <section className="bg-marine-900/90 border border-marine-800/90 rounded-3xl p-5 sm:p-7 shadow-xl">
        <div className="flex items-center gap-2.5 pb-4 border-b border-marine-800">
          <User className="w-5 h-5 text-cyan-400" />
          <h2 className="text-base sm:text-lg font-black text-white">{t('settings.profileTitle')}</h2>
        </div>

        <form onSubmit={handleSaveProfile} className="mt-5 space-y-4">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-cyan-600 to-emerald-500 text-marine-950 font-black text-xl flex items-center justify-center shadow-neon-cyan border border-white/20 shrink-0">
              {initials}
            </div>
            <div>
              <p className="text-sm font-black text-white">{user?.full_name || t('settings.defaultName')}</p>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-xs text-slate-400 font-mono">{user?.email}</span>
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  {t('common.active')}
                </span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            <div>
              <label className="block text-xs font-extrabold uppercase text-slate-400 mb-1.5">
                {t('settings.fullName')}
              </label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder={t('settings.fullNamePlaceholder')}
                className="w-full bg-marine-950 border border-marine-700 rounded-2xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 focus:border-cyan-400 transition"
              />
            </div>

            <div>
              <label className="block text-xs font-extrabold uppercase text-slate-400 mb-1.5">
                {t('settings.emailReadOnly')}
              </label>
              <div className="relative">
                <input
                  type="email"
                  disabled
                  value={user?.email || ''}
                  className="w-full bg-marine-950/50 border border-marine-800 text-slate-400 rounded-2xl px-4 py-2.5 text-sm cursor-not-allowed"
                />
                <ShieldCheck className="w-4 h-4 text-emerald-400 absolute right-3.5 top-3.5" />
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between pt-2">
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <Calendar className="w-3.5 h-3.5" />
              <span>{t('settings.memberSince')} {formattedDate}</span>
            </div>

            <button
              type="submit"
              disabled={saving}
              className="px-5 py-2.5 rounded-2xl bg-cyan-500 hover:bg-cyan-400 text-marine-950 font-black text-xs sm:text-sm flex items-center gap-2 shadow-neon-cyan active:scale-95 transition disabled:opacity-50"
            >
              <Save className="w-4 h-4 stroke-[2.5]" />
              <span>{saving ? t('settings.savingBtn') : t('settings.saveProfileBtn')}</span>
            </button>
          </div>
        </form>
      </section>

      {/* 2. SECCIÓN DE UNIDADES DE MEDIDA */}
      <section className="bg-marine-900/90 border border-marine-800/90 rounded-3xl p-5 sm:p-7 shadow-xl">
        <div className="flex items-center gap-2.5 pb-4 border-b border-marine-800">
          <Scale className="w-5 h-5 text-cyan-400" />
          <h2 className="text-base sm:text-lg font-black text-white">{t('settings.unitsTitle')}</h2>
        </div>

        <p className="text-xs sm:text-sm text-slate-400 mt-4 mb-4">
          {t('settings.unitsDesc')}
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Opción Litros */}
          <button
            type="button"
            onClick={() => handleUnitChange('liters')}
            className={`p-4 rounded-2xl border text-left transition-all relative overflow-hidden ${
              selectedUnits === 'liters'
                ? 'bg-gradient-to-tr from-cyan-950/60 to-marine-800/90 border-cyan-400 shadow-neon-cyan/20'
                : 'bg-marine-950/60 border-marine-800 hover:border-marine-700'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-black text-white">{t('settings.metricTitle')}</span>
              {selectedUnits === 'liters' && (
                <div className="w-6 h-6 rounded-full bg-cyan-400 text-marine-950 flex items-center justify-center">
                  <Check className="w-4 h-4 stroke-[3]" />
                </div>
              )}
            </div>
            <div className="text-2xl font-black text-cyan-300">{t('settings.metricUnit')}</div>
            <p className="text-xs text-slate-400 mt-1">
              {t('settings.metricDesc')}
            </p>
          </button>

          {/* Opción Galones */}
          <button
            type="button"
            onClick={() => handleUnitChange('gallons')}
            className={`p-4 rounded-2xl border text-left transition-all relative overflow-hidden ${
              selectedUnits === 'gallons'
                ? 'bg-gradient-to-tr from-cyan-950/60 to-marine-800/90 border-cyan-400 shadow-neon-cyan/20'
                : 'bg-marine-950/60 border-marine-800 hover:border-marine-700'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-black text-white">{t('settings.imperialTitle')}</span>
              {selectedUnits === 'gallons' && (
                <div className="w-6 h-6 rounded-full bg-cyan-400 text-marine-950 flex items-center justify-center">
                  <Check className="w-4 h-4 stroke-[3]" />
                </div>
              )}
            </div>
            <div className="text-2xl font-black text-cyan-300">{t('settings.imperialUnit')}</div>
            <p className="text-xs text-slate-400 mt-1">
              {t('settings.imperialDesc')}
            </p>
          </button>
        </div>
      </section>

      {/* 3. SECCIÓN DE SUSCRIPCIÓN FREEMIUM */}
      <section className="bg-gradient-to-b from-marine-900 to-marine-950 border border-marine-800 rounded-3xl p-5 sm:p-7 shadow-2xl relative overflow-hidden">
        {/* Glow de fondo */}
        <div className="absolute top-0 right-0 w-64 h-64 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="flex items-center justify-between pb-4 border-b border-marine-800">
          <div className="flex items-center gap-2.5">
            <Crown className="w-5 h-5 text-amber-400" />
            <h2 className="text-base sm:text-lg font-black text-white">{t('settings.subTitle')}</h2>
          </div>
          <span className="text-xs font-black uppercase px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
            {t('settings.currentPlan')}
          </span>
        </div>

        {/* Tarjeta de Comparación Freemium */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mt-5">
          {/* Beneficios Incluidos en Free */}
          <div className="bg-marine-950/80 border border-marine-800 rounded-2xl p-4 sm:p-5">
            <div className="flex items-center gap-2 mb-3">
              <Layers className="w-4 h-4 text-cyan-400" />
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                {t('settings.includedTitle')}
              </h3>
            </div>
            <ul className="space-y-2.5 text-xs text-slate-300">
              <li className="flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                <span><strong>{t('settings.incTank')}</strong></span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>{t('settings.incPred')}</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>{t('settings.incAI')}</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>{t('settings.incPush')}</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>{t('settings.incCloud')}</span>
              </li>
            </ul>
          </div>

          {/* Próximas funciones en Premium */}
          <div className="bg-marine-950/80 border border-purple-500/30 rounded-2xl p-4 sm:p-5 relative">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-purple-400" />
                <h3 className="text-sm font-bold text-purple-300 uppercase tracking-wider">
                  {t('settings.proTitle')}
                </h3>
              </div>
              <span className="text-[10px] font-black uppercase px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/40">
                {t('settings.phase2')}
              </span>
            </div>
            <ul className="space-y-2.5 text-xs text-slate-400">
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-400 shrink-0" />
                <span>{t('settings.proTanks')}</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-400 shrink-0" />
                <span>{t('settings.proReports')}</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-400 shrink-0" />
                <span>{t('settings.proAlerts')}</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-400 shrink-0" />
                <span>{t('settings.proControllers')}</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-400 shrink-0" />
                <span>{t('settings.proSupport')}</span>
              </li>
            </ul>
          </div>
        </div>

        {/* Botón Inactivo Upgrade a Premium */}
        <div className="mt-6 pt-5 border-t border-marine-800/80 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-extrabold text-white">AquaPulse Pro / Premium</span>
              <span className="text-xs text-purple-300 font-bold">{t('settings.proPrice')}</span>
            </div>
            <p className="text-xs text-slate-400">
              {t('settings.gatewayNotice')}
            </p>
          </div>

          <button
            type="button"
            disabled
            className="w-full sm:w-auto min-h-[46px] px-6 rounded-2xl bg-gradient-to-r from-purple-700 via-indigo-600 to-purple-800 text-purple-200 font-extrabold text-xs sm:text-sm flex items-center justify-center gap-2 opacity-60 cursor-not-allowed border border-purple-400/30 shadow-none"
            title={t('settings.gatewayNotice')}
          >
            <Lock className="w-4 h-4 text-purple-300" />
            <span>{t('settings.upgradeBtn')}</span>
          </button>
        </div>
      </section>

      {/* ACCESO AL PANEL DE ADMINISTRADOR (SOLO SI ES ADMIN) */}
      {user?.is_admin && (
        <section className="bg-gradient-to-r from-amber-950/40 via-marine-900/90 to-cyan-950/40 border border-amber-500/40 rounded-3xl p-5 sm:p-7 shadow-xl relative overflow-hidden">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex items-center gap-3.5">
              <div className="w-12 h-12 rounded-2xl bg-amber-500/20 text-amber-300 border border-amber-500/40 flex items-center justify-center shrink-0">
                <ShieldCheck className="w-6 h-6" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-black text-white">{t('admin.title')}</h3>
                  <span className="text-[10px] font-black uppercase px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40">
                    SUPERADMIN
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5 max-w-xl">
                  {t('admin.settingsShortcutDesc')}
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => {
                triggerHaptic();
                if (onOpenAdmin) onOpenAdmin();
              }}
              className="w-full sm:w-auto px-5 py-3 rounded-2xl bg-gradient-to-r from-amber-500 to-cyan-400 hover:brightness-110 text-marine-950 font-black text-xs sm:text-sm flex items-center justify-center gap-2 shadow-neon-amber transition active:scale-95 shrink-0"
            >
              <ShieldCheck className="w-4 h-4 text-marine-950 stroke-[2.5]" />
              <span>{t('admin.settingsShortcut')}</span>
            </button>
          </div>
        </section>
      )}

      {/* 4. SECCIÓN DE SEGURIDAD Y CIERRE DE SESIÓN */}
      <section className="bg-marine-900/90 border border-marine-800/90 rounded-3xl p-5 sm:p-7 shadow-xl">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-black text-white">{t('settings.activeSession')}</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              {t('settings.sessionDesc', { email: user?.email })}
            </p>
          </div>

          <button
            type="button"
            onClick={handleLogoutClick}
            className="px-4 py-2.5 rounded-2xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 hover:border-rose-500/60 font-bold text-xs sm:text-sm flex items-center gap-2 active:scale-95 transition"
          >
            <LogOut className="w-4 h-4" />
            <span>{t('settings.logoutBtn')}</span>
          </button>
        </div>
      </section>
    </div>
  );
}
