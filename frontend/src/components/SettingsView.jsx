import React, { useState } from 'react';
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

export default function SettingsView({ onOpenAuthModal }) {
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
      setStatusMessage({ type: 'success', text: '¡Ajustes guardados correctamente!' });
      setTimeout(() => setStatusMessage(null), 3500);
    } catch (err) {
      setStatusMessage({ type: 'error', text: err.message || 'Error al guardar los ajustes' });
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
        text: `Preferencia actualizada a ${unit === 'liters' ? 'Litros (L)' : 'Galones US (gal)'}`
      });
      setTimeout(() => setStatusMessage(null), 3000);
    } catch (err) {
      setStatusMessage({ type: 'error', text: 'Error al cambiar la unidad de medida' });
    } finally {
      setSaving(false);
    }
  };

  const handleLogoutClick = () => {
    triggerHaptic();
    if (window.confirm('¿Seguro que deseas cerrar la sesión en AquaPulse?')) {
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
          <h2 className="text-2xl font-black text-white mb-2">Sesión Requerida</h2>
          <p className="text-sm text-slate-400 max-w-md mx-auto mb-6">
            Inicia sesión o crea tu cuenta gratuita para personalizar tus unidades de medida, gestionar tu perfil y acceder a tu suscripción.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <button
              onClick={() => openAuthModal('login')}
              className="px-6 py-3 rounded-2xl bg-gradient-to-r from-cyan-500 to-cyan-400 text-marine-950 font-black text-sm shadow-neon-cyan hover:brightness-110 active:scale-95 transition"
            >
              Iniciar Sesión
            </button>
            <button
              onClick={() => openAuthModal('register')}
              className="px-6 py-3 rounded-2xl bg-marine-950 border border-marine-700 text-slate-200 font-bold text-sm hover:border-cyan-400 active:scale-95 transition"
            >
              Crear Cuenta Free
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
    ? new Date(user.created_at).toLocaleDateString('es-ES', {
        year: 'numeric',
        month: 'long',
        day: 'numeric'
      })
    : 'Activo';

  return (
    <div className="max-w-4xl mx-auto px-4 py-6 sm:py-8 pb-28 sm:pb-12 space-y-6 sm:space-y-8 animate-fadeIn">
      {/* Encabezado */}
      <div>
        <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight flex items-center gap-3">
          <span>Ajustes de la Cuenta</span>
          <span className="text-xs uppercase font-black px-2.5 py-1 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-400/40">
            Freemium
          </span>
        </h1>
        <p className="text-xs sm:text-sm text-slate-400 mt-1">
          Configuración personal, unidades volumétricas y estado de suscripción comercial.
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
          <h2 className="text-base sm:text-lg font-black text-white">Perfil de Acuarista</h2>
        </div>

        <form onSubmit={handleSaveProfile} className="mt-5 space-y-4">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-cyan-600 to-emerald-500 text-marine-950 font-black text-xl flex items-center justify-center shadow-neon-cyan border border-white/20 shrink-0">
              {initials}
            </div>
            <div>
              <p className="text-sm font-black text-white">{user?.full_name || 'Acuarista Reef'}</p>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-xs text-slate-400 font-mono">{user?.email}</span>
                <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
                  Activo
                </span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            <div>
              <label className="block text-xs font-extrabold uppercase text-slate-400 mb-1.5">
                Nombre Completo
              </label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Tu nombre o alias"
                className="w-full bg-marine-950 border border-marine-700 rounded-2xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 focus:border-cyan-400 transition"
              />
            </div>

            <div>
              <label className="block text-xs font-extrabold uppercase text-slate-400 mb-1.5">
                Correo Electrónico (Solo Lectura)
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
              <span>Miembro desde: {formattedDate}</span>
            </div>

            <button
              type="submit"
              disabled={saving}
              className="px-5 py-2.5 rounded-2xl bg-cyan-500 hover:bg-cyan-400 text-marine-950 font-black text-xs sm:text-sm flex items-center gap-2 shadow-neon-cyan active:scale-95 transition disabled:opacity-50"
            >
              <Save className="w-4 h-4 stroke-[2.5]" />
              <span>{saving ? 'Guardando...' : 'Guardar Perfil'}</span>
            </button>
          </div>
        </form>
      </section>

      {/* 2. SECCIÓN DE UNIDADES DE MEDIDA */}
      <section className="bg-marine-900/90 border border-marine-800/90 rounded-3xl p-5 sm:p-7 shadow-xl">
        <div className="flex items-center gap-2.5 pb-4 border-b border-marine-800">
          <Scale className="w-5 h-5 text-cyan-400" />
          <h2 className="text-base sm:text-lg font-black text-white">Unidades de Medida</h2>
        </div>

        <p className="text-xs sm:text-sm text-slate-400 mt-4 mb-4">
          Selecciona el sistema de volumen para el cálculo de dosificaciones, capacidad de acuarios y diluciones en cambios de agua:
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
              <span className="text-sm font-black text-white">Sistema Métrico</span>
              {selectedUnits === 'liters' && (
                <div className="w-6 h-6 rounded-full bg-cyan-400 text-marine-950 flex items-center justify-center">
                  <Check className="w-4 h-4 stroke-[3]" />
                </div>
              )}
            </div>
            <div className="text-2xl font-black text-cyan-300">Litros (L)</div>
            <p className="text-xs text-slate-400 mt-1">
              Estándar internacional para volúmenes netos y concentración química.
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
              <span className="text-sm font-black text-white">Sistema Imperial US</span>
              {selectedUnits === 'gallons' && (
                <div className="w-6 h-6 rounded-full bg-cyan-400 text-marine-950 flex items-center justify-center">
                  <Check className="w-4 h-4 stroke-[3]" />
                </div>
              )}
            </div>
            <div className="text-2xl font-black text-cyan-300">Galones US (gal)</div>
            <p className="text-xs text-slate-400 mt-1">
              Utilizado comúnmente en tanques comerciales de EE. UU. (1 gal ≈ 3.785 L).
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
            <h2 className="text-base sm:text-lg font-black text-white">Suscripción y Límites</h2>
          </div>
          <span className="text-xs font-black uppercase px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
            Plan Actual: Gratuito (Free)
          </span>
        </div>

        {/* Tarjeta de Comparación Freemium */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-5 mt-5">
          {/* Beneficios Incluidos en Free */}
          <div className="bg-marine-950/80 border border-marine-800 rounded-2xl p-4 sm:p-5">
            <div className="flex items-center gap-2 mb-3">
              <Layers className="w-4 h-4 text-cyan-400" />
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                Incluido en tu Plan Gratuito
              </h3>
            </div>
            <ul className="space-y-2.5 text-xs text-slate-300">
              <li className="flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                <span><strong>1 Acuario Activo</strong> con biometría completa</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Predicción de consumo de <strong>dKH y Calcio</strong> a 14 días</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Escáner de tests con <strong>Inteligencia Artificial</strong></span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Recordatorios locales con Web Notifications</span>
              </li>
              <li className="flex items-center gap-2">
                <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Persistencia en la nube PostgreSQL</span>
              </li>
            </ul>
          </div>

          {/* Próximas funciones en Premium */}
          <div className="bg-marine-950/80 border border-purple-500/30 rounded-2xl p-4 sm:p-5 relative">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <Sparkles className="w-4 h-4 text-purple-400" />
                <h3 className="text-sm font-bold text-purple-300 uppercase tracking-wider">
                  Beneficios AquaPulse Pro
                </h3>
              </div>
              <span className="text-[10px] font-black uppercase px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/40">
                Fase 2
              </span>
            </div>
            <ul className="space-y-2.5 text-xs text-slate-400">
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-400 shrink-0" />
                <span><strong>Acuarios y Sumps Ilimitados</strong> en una sola cuenta</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-400 shrink-0" />
                <span>Exportación de informes a <strong>PDF y CSV</strong> para concursos</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-400 shrink-0" />
                <span>Alertas push instantáneas vía <strong>Telegram / WhatsApp</strong></span>
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-400 shrink-0" />
                <span>Integración directa con controladores <strong>Apex / Hydros</strong></span>
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-purple-400 shrink-0" />
                <span>Soporte prioritario 24/7 para tanques SPS exigentes</span>
              </li>
            </ul>
          </div>
        </div>

        {/* Botón Inactivo Upgrade a Premium */}
        <div className="mt-6 pt-5 border-t border-marine-800/80 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-extrabold text-white">AquaPulse Pro / Premium</span>
              <span className="text-xs text-purple-300 font-bold">$9.99 USD / mes</span>
            </div>
            <p className="text-xs text-slate-400">
              La pasarela de pago estará disponible en la próxima actualización comercial.
            </p>
          </div>

          <button
            type="button"
            disabled
            className="w-full sm:w-auto min-h-[46px] px-6 rounded-2xl bg-gradient-to-r from-purple-700 via-indigo-600 to-purple-800 text-purple-200 font-extrabold text-xs sm:text-sm flex items-center justify-center gap-2 opacity-60 cursor-not-allowed border border-purple-400/30 shadow-none"
            title="La pasarela de pago estará disponible en la próxima fase comercial"
          >
            <Lock className="w-4 h-4 text-purple-300" />
            <span>Upgrade a Premium (Próximamente)</span>
          </button>
        </div>
      </section>

      {/* 4. SECCIÓN DE SEGURIDAD Y CIERRE DE SESIÓN */}
      <section className="bg-marine-900/90 border border-marine-800/90 rounded-3xl p-5 sm:p-7 shadow-xl">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-black text-white">Sesión Activa</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Conectado como <strong className="text-cyan-300">{user?.email}</strong>. Todos los datos están aislados bajo tu cuenta.
            </p>
          </div>

          <button
            type="button"
            onClick={handleLogoutClick}
            className="px-4 py-2.5 rounded-2xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 hover:border-rose-500/60 font-bold text-xs sm:text-sm flex items-center gap-2 active:scale-95 transition"
          >
            <LogOut className="w-4 h-4" />
            <span>Cerrar Sesión</span>
          </button>
        </div>
      </section>
    </div>
  );
}
