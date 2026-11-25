import React from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronDown, RefreshCw, Bell, User, LogIn, Globe, ShieldCheck, Pencil } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export default function Navbar({
  tanks,
  activeTank,
  onSelectTank,
  onOpenNewTankModal,
  onOpenEditTankModal,
  onOpenNotificationModal,
  onOpenSettings,
  onOpenAdmin,
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
        {/* Barra de navegación - Cabecera izquierda */}
        <div className="flex items-center space-x-3">
          {/* AQUÍ ESTÁ EL NUEVO LOGO DEL ARRECIFE */}
          <img 
            src="/logo-reef-icon.png" 
            alt="AquaReef Logo" 
            onError={(e) => { e.currentTarget.src = '/logo-reef.png'; }}
            className="w-12 h-12 rounded-2xl shadow-lg shadow-cyan-500/10 border border-cyan-500/20 object-cover shrink-0" 
          />
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold text-white tracking-tight">AquaReef</h1>
              <span className="text-[10px] font-bold text-cyan-400 bg-cyan-950/50 border border-cyan-800/80 px-1.5 py-0.5 rounded-full uppercase">PWA</span>
            </div>
            <p className="text-xs text-gray-400 hidden sm:block">Gestión Predictiva Multi-Usuario para Acuarios de Arrecife</p>
          </div>
        </div>

        {/* Selector de Acuario & Grupo de Botones de la Cabecera */}
        <div className="flex items-center gap-2 sm:gap-3">
          {tanks.length > 0 && (
            <div className="flex items-center gap-1.5">
              <div className="relative">
                <select
                  value={activeTank ? activeTank.id : ''}
                  onChange={(e) => {
                    triggerHaptic();
                    const selected = tanks.find((t) => t.id === parseInt(e.target.value));
                    if (selected) onSelectTank(selected);
                  }}
                  className="appearance-none min-h-[40px] sm:min-h-[44px] bg-marine-900 text-slate-100 text-xs sm:text-sm font-bold pl-3 pr-8 sm:pl-3.5 sm:pr-9 py-2 rounded-2xl border border-marine-700 hover:border-cyan-400 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 cursor-pointer transition shadow-inner max-w-[130px] sm:max-w-none truncate"
                >
                  {tanks.map((tank) => (
                    <option key={tank.id} value={tank.id}>
                      {tank.name} ({formatTankVolume(tank.volume_liters)})
                    </option>
                  ))}
                </select>
                <ChevronDown className="w-4 h-4 text-cyan-400 absolute right-2.5 sm:right-3 top-3 sm:top-3.5 pointer-events-none" />
              </div>

              {activeTank && onOpenEditTankModal && (
                <button
                  type="button"
                  onClick={() => {
                    triggerHaptic();
                    onOpenEditTankModal(activeTank);
                  }}
                  title="Editar Acuario / Litraje"
                  aria-label="Editar Acuario / Litraje"
                  className="min-h-[40px] min-w-[40px] sm:min-h-[44px] sm:min-w-[44px] px-2.5 bg-marine-900 hover:bg-cyan-500/20 text-cyan-400 border border-marine-700 hover:border-cyan-400/60 rounded-2xl flex items-center justify-center gap-1.5 transition active:scale-95 shadow-inner"
                >
                  <Pencil className="w-3.5 h-3.5" />
                  <span className="hidden lg:inline text-xs font-bold">Editar</span>
                </button>
              )}
            </div>
          )}

          {/* Grupo de Botones de la Cabecera */}
          <div className="flex items-center space-x-2">
            {/* Oculto en móvil, visible en PC */}
            <div className="hidden md:flex items-center space-x-2">
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

              {/* Botón de Recarga (🔄) */}
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

              {/* Botón Acceso Admin (🛡️) (Solo si is_admin = true) */}
              {isAuthenticated && user?.is_admin && (
                <button
                  onClick={() => {
                    triggerHaptic();
                    if (onOpenAdmin) onOpenAdmin();
                  }}
                  title="Panel de Control de Administrador"
                  className="min-h-[44px] px-3 rounded-2xl bg-gradient-to-r from-amber-500/20 via-cyan-500/20 to-amber-500/10 border border-amber-500/50 hover:border-amber-400 text-amber-300 font-black text-xs flex items-center gap-1.5 shadow-neon-amber transition active:scale-95"
                >
                  <ShieldCheck className="w-4 h-4 text-amber-400" />
                  <span>{t('admin.navLink')}</span>
                </button>
              )}

              {/* Perfil de Usuario / Iniciar Sesión (P) */}
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
                  <span className="text-[10px] font-black uppercase px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
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
                  <span>{t('nav.login')}</span>
                </button>
              )}
            </div>

            {/* Visible siempre (Móvil y PC) */}
            <button
              onClick={() => {
                triggerHaptic();
                if (onOpenNotificationModal) onOpenNotificationModal();
              }}
              title={t('nav.notificationsTitle')}
              aria-label={t('nav.notificationsTitle')}
              className="bg-cyan-900/50 hover:bg-cyan-800/60 text-cyan-400 border border-cyan-500/30 p-2 sm:p-2.5 rounded-full flex items-center justify-center transition active:scale-90 shadow-sm"
            >
              <Bell className="w-5 h-5 text-cyan-400" />
            </button>

            {/* ELIMINADO: el botón "+" de aquí arriba, ya que existe el botón gigante flotante abajo */}
          </div>
        </div>
      </div>
    </header>
  );
}
