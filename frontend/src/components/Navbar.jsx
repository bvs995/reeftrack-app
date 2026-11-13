import React from 'react';
import { useTranslation } from 'react-i18next';
import { Waves, Plus, ChevronDown, RefreshCw, Bell, User, LogIn, Globe } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function Navbar({
  tanks,
  activeTank,
  onSelectTank,
  onOpenNewTankModal,
  onOpenNotificationModal,
  onOpenSettings,
  onRefresh,
  loading
}) {
  const { t, i18n } = useTranslation();
  const { user, isAuthenticated, openAuthModal, unitPreference } = useAuth();

  const currentLang = (i18n.language || 'es').toLowerCase().startsWith('en') ? 'en' : 'es';

  const triggerHaptic = () => {
    if (typeof navigator !== 'undefined' && navigator.vibrate) {
      navigator.vibrate(15);
    }
  };

  const handleLanguageChange = (lang) => {
    triggerHaptic();
    i18n.changeLanguage(lang);
  };

  const initials = (user?.full_name || user?.email || 'A')
    .split(' ')
    .map((n) => n[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  const formatTankVolume = (liters) => {
    if (unitPreference === 'gallons') {
      const gallons = Math.round(liters * 0.264172);
      return `${gallons} ${t('common.gallonsShort')}`;
    }
    return `${liters}${t('common.litersShort')}`;
  };

  return (
    <header className="sticky top-0 z-40 bg-marine-950/90 backdrop-blur-xl border-b border-marine-800/90 px-3 sm:px-6 py-3 shadow-lg">
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-3">
        {/* Brand Náutico Neón */}
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-gradient-to-tr from-cyan-600 via-cyan-400 to-emerald-400 flex items-center justify-center shadow-neon-cyan border border-white/20 shrink-0">
            <Waves className="w-6 h-6 text-marine-950 stroke-[2.5]" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="font-black text-xl tracking-tight bg-gradient-to-r from-cyan-300 via-sky-200 to-emerald-300 bg-clip-text text-transparent drop-shadow-[0_0_12px_rgba(6,182,212,0.5)]">
                {t('nav.brand')}
              </span>
              <span className="text-[10px] font-black tracking-wider uppercase px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-400/50">
                {t('nav.pwa')}
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-medium hidden sm:block">
              {t('nav.subtitle')}
            </p>
          </div>
        </div>

        {/* Selector de Acuario & Acciones Táctiles */}
        <div className="flex items-center gap-2">
          {tanks.length > 0 && (
            <div className="relative">
              <select
                value={activeTank ? activeTank.id : ''}
                onChange={(e) => {
                  triggerHaptic();
                  const selected = tanks.find((t) => t.id === parseInt(e.target.value));
                  if (selected) onSelectTank(selected);
                }}
                className="appearance-none min-h-[44px] bg-marine-900 text-slate-100 text-xs sm:text-sm font-bold pl-3.5 pr-9 py-2 rounded-2xl border border-marine-700 hover:border-cyan-400 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 cursor-pointer transition shadow-inner"
              >
                {tanks.map((tank) => (
                  <option key={tank.id} value={tank.id}>
                    {tank.name} ({formatTankVolume(tank.volume_liters)})
                  </option>
                ))}
              </select>
              <ChevronDown className="w-4 h-4 text-cyan-400 absolute right-3 top-3.5 pointer-events-none" />
            </div>
          )}

          {/* Selector Discreto de Idioma (ES / EN) */}
          <div
            className="flex items-center bg-marine-900 border border-marine-700/80 rounded-2xl p-1 shadow-inner"
            role="group"
            aria-label="Selector de idioma"
          >
            <button
              type="button"
              onClick={() => handleLanguageChange('es')}
              className={`min-h-[32px] px-2.5 py-1 rounded-xl text-xs font-black transition-all ${
                currentLang === 'es'
                  ? 'bg-gradient-to-r from-cyan-500 to-cyan-400 text-marine-950 shadow-neon-cyan/50 font-black'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="Español"
              aria-label="Cambiar idioma a Español"
            >
              ES
            </button>
            <button
              type="button"
              onClick={() => handleLanguageChange('en')}
              className={`min-h-[32px] px-2.5 py-1 rounded-xl text-xs font-black transition-all ${
                currentLang === 'en'
                  ? 'bg-gradient-to-r from-cyan-500 to-cyan-400 text-marine-950 shadow-neon-cyan/50 font-black'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
              title="English (US)"
              aria-label="Switch language to English (US)"
            >
              EN
            </button>
          </div>

          {/* Botón de Notificaciones */}
          <button
            onClick={() => {
              triggerHaptic();
              if (onOpenNotificationModal) onOpenNotificationModal();
            }}
            title={t('nav.notificationsTitle')}
            className="w-11 h-11 rounded-2xl bg-marine-900 border border-marine-700/80 text-slate-300 hover:text-cyan-300 hover:border-cyan-400 flex items-center justify-center transition active:scale-90"
            aria-label={t('nav.notificationsTitle')}
          >
            <Bell className="w-4 h-4 text-cyan-400" />
          </button>

          {/* Botón de Recarga */}
          <button
            onClick={() => {
              triggerHaptic();
              onRefresh();
            }}
            disabled={loading}
            title={t('nav.refreshTitle')}
            className="w-11 h-11 rounded-2xl bg-marine-900 border border-marine-700/80 text-slate-300 hover:text-cyan-300 hover:border-cyan-400 flex items-center justify-center transition active:scale-90 disabled:opacity-50"
            aria-label={t('nav.refreshTitle')}
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-cyan-400' : ''}`} />
          </button>

          {/* Botón Nuevo Acuario */}
          <button
            onClick={() => {
              triggerHaptic();
              onOpenNewTankModal();
            }}
            className="min-h-[44px] px-3.5 rounded-2xl bg-gradient-to-r from-cyan-500 to-cyan-400 hover:from-cyan-400 hover:to-cyan-300 text-marine-950 font-black text-xs sm:text-sm flex items-center gap-1.5 shadow-neon-cyan active:scale-95 transition"
          >
            <Plus className="w-4 h-4 stroke-[3]" />
            <span className="hidden sm:inline">{t('nav.newTank')}</span>
          </button>

          {/* Perfil de Usuario / Iniciar Sesión */}
          {isAuthenticated ? (
            <button
              onClick={() => {
                triggerHaptic();
                if (onOpenSettings) onOpenSettings();
              }}
              title={`Perfil: ${user?.email} (${t('common.free')})`}
              className="min-h-[44px] px-2.5 sm:px-3 rounded-2xl bg-marine-900 border border-marine-700/80 hover:border-cyan-400/80 flex items-center gap-2 transition active:scale-95"
            >
              <div className="w-7 h-7 rounded-xl bg-gradient-to-tr from-cyan-600 to-emerald-500 text-marine-950 font-black text-xs flex items-center justify-center">
                {initials}
              </div>
              <span className="text-[10px] font-black uppercase px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 hidden sm:inline">
                {user?.subscription_tier?.toUpperCase() || t('common.free')}
              </span>
            </button>
          ) : (
            <button
              onClick={() => {
                triggerHaptic();
                openAuthModal('login');
              }}
              className="min-h-[44px] px-3 rounded-2xl bg-marine-900 border border-cyan-500/50 text-cyan-300 font-bold text-xs flex items-center gap-1.5 hover:bg-cyan-500/10 active:scale-95 transition"
            >
              <LogIn className="w-4 h-4" />
              <span className="hidden sm:inline">{t('nav.login')}</span>
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
