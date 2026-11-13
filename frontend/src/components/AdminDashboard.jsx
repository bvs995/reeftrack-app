import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../context/AuthContext';
import {
  fetchAdminUsers,
  updateAdminUser,
  deleteAdminUser
} from '../api';
import {
  ShieldAlert,
  ShieldCheck,
  Users,
  Crown,
  Droplets,
  Activity,
  Search,
  RefreshCw,
  UserX,
  UserCheck,
  Trash2,
  ArrowLeft,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  Layers,
  ChevronDown,
  Mail,
  Calendar,
  Lock
} from 'lucide-react';

export default function AdminDashboard({ onBackToDashboard }) {
  const { t, i18n } = useTranslation();
  const { user, isAdmin, loading: authLoading } = useAuth();

  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [tierFilter, setTierFilter] = useState('all'); // 'all' | 'free' | 'premium'
  const [statusFilter, setStatusFilter] = useState('all'); // 'all' | 'active' | 'suspended'
  const [actionUserId, setActionUserId] = useState(null);
  const [userToDelete, setUserToDelete] = useState(null);
  const [toast, setToast] = useState(null);

  const triggerHaptic = () => {
    if (typeof navigator !== 'undefined' && navigator.vibrate) {
      navigator.vibrate(15);
    }
  };

  const showToast = (type, message) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 4000);
  };

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchAdminUsers();
      setUsers(data);
    } catch (err) {
      console.error('Error cargando usuarios en admin:', err);
      showToast('error', err.message || 'Error al cargar usuarios.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAdmin) {
      loadUsers();
    }
  }, [isAdmin, loadUsers]);

  // Filtrado de usuarios en cliente (declarado incondicionalmente para cumplir las reglas de hooks)
  const filteredUsers = useMemo(() => {
    if (!users || !Array.isArray(users)) return [];
    return users.filter((u) => {
      // Búsqueda por texto (email o nombre)
      const q = searchQuery.toLowerCase().trim();
      const matchQuery =
        !q ||
        (u.email && u.email.toLowerCase().includes(q)) ||
        (u.full_name && u.full_name.toLowerCase().includes(q));

      // Filtro de plan
      const matchTier =
        tierFilter === 'all' ||
        (tierFilter === 'premium' && u.subscription_tier === 'premium') ||
        (tierFilter === 'free' && u.subscription_tier !== 'premium');

      // Filtro de estado
      const matchStatus =
        statusFilter === 'all' ||
        (statusFilter === 'active' && u.is_active) ||
        (statusFilter === 'suspended' && !u.is_active);

      return matchQuery && matchTier && matchStatus;
    });
  }, [users, searchQuery, tierFilter, statusFilter]);

  // Métricas globales (declarado incondicionalmente)
  const stats = useMemo(() => {
    if (!users || !Array.isArray(users)) {
      return { total: 0, active: 0, premium: 0, tanks: 0, measurements: 0 };
    }
    const total = users.length;
    const active = users.filter((u) => u.is_active).length;
    const premium = users.filter((u) => u.subscription_tier === 'premium').length;
    const tanks = users.reduce((acc, u) => acc + (u.tank_count || 0), 0);
    const measurements = users.reduce((acc, u) => acc + (u.measurement_count || 0), 0);
    return { total, active, premium, tanks, measurements };
  }, [users]);

  // Estado de carga inicial de autenticación
  if (authLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-20 text-center text-slate-400">
        <RefreshCw className="w-8 h-8 animate-spin mx-auto text-cyan-400 mb-3" />
        <p className="text-sm font-bold">{t('common.loading')}</p>
      </div>
    );
  }

  // Si el usuario no es admin o no está logueado: Acceso Restringido
  if (!isAdmin) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-16 text-center animate-fadeIn">
        <div className="bg-marine-900/90 border border-rose-500/30 rounded-3xl p-8 sm:p-12 shadow-2xl relative overflow-hidden backdrop-blur-xl">
          <div className="w-20 h-20 rounded-3xl bg-rose-500/10 text-rose-400 border border-rose-500/30 flex items-center justify-center mx-auto mb-6 shadow-neon-rose">
            <ShieldAlert className="w-10 h-10 stroke-[2.2]" />
          </div>
          <span className="text-[11px] font-black uppercase tracking-widest px-3 py-1 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/40 inline-block mb-3">
            HTTP 403 • FORBIDDEN
          </span>
          <h2 className="text-2xl sm:text-3xl font-black text-white mb-3">
            {t('admin.accessDeniedTitle')}
          </h2>
          <p className="text-sm text-slate-300 max-w-lg mx-auto mb-8 leading-relaxed">
            {t('admin.accessDeniedDesc')}
          </p>
          <div className="flex justify-center">
            <button
              onClick={() => {
                triggerHaptic();
                if (onBackToDashboard) onBackToDashboard();
              }}
              className="px-6 py-3 rounded-2xl bg-cyan-500 hover:bg-cyan-400 text-marine-950 font-black text-sm flex items-center gap-2 shadow-neon-cyan transition active:scale-95"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>{t('admin.backToDashboard')}</span>
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Manejar cambio de estado Activo/Suspendido
  const handleToggleActive = async (targetUser) => {
    triggerHaptic();
    if (targetUser.id === user?.id) {
      showToast('error', t('admin.actions.selfProtect'));
      return;
    }

    const nextState = !targetUser.is_active;
    setActionUserId(targetUser.id);
    try {
      const updated = await updateAdminUser(targetUser.id, { is_active: nextState });
      setUsers((prev) =>
        prev.map((u) => (u.id === targetUser.id ? { ...u, is_active: updated.is_active } : u))
      );
      showToast('success', t('admin.actions.statusSuccess'));
    } catch (err) {
      showToast('error', err.message || 'Error al cambiar estado.');
    } finally {
      setActionUserId(null);
    }
  };

  // Manejar cambio de Plan Freemium (Free <-> Premium)
  const handleToggleTier = async (targetUser) => {
    triggerHaptic();
    const nextTier = targetUser.subscription_tier === 'premium' ? 'free' : 'premium';
    setActionUserId(targetUser.id);
    try {
      const updated = await updateAdminUser(targetUser.id, { subscription_tier: nextTier });
      setUsers((prev) =>
        prev.map((u) =>
          u.id === targetUser.id ? { ...u, subscription_tier: updated.subscription_tier } : u
        )
      );
      showToast('success', t('admin.actions.tierSuccess'));
    } catch (err) {
      showToast('error', err.message || 'Error al cambiar plan.');
    } finally {
      setActionUserId(null);
    }
  };

  // Manejar eliminación de usuario
  const handleConfirmDelete = async () => {
    if (!userToDelete) return;
    triggerHaptic();

    if (userToDelete.id === user?.id) {
      showToast('error', t('admin.actions.selfProtect'));
      setUserToDelete(null);
      return;
    }

    setActionUserId(userToDelete.id);
    try {
      await deleteAdminUser(userToDelete.id);
      setUsers((prev) => prev.filter((u) => u.id !== userToDelete.id));
      showToast('success', t('admin.actions.deleteSuccess'));
      setUserToDelete(null);
    } catch (err) {
      showToast('error', err.message || 'Error al eliminar usuario.');
    } finally {
      setActionUserId(null);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return '—';
    try {
      const d = new Date(dateString);
      return d.toLocaleDateString(i18n.language || 'es-ES', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
      });
    } catch {
      return dateString;
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 py-6 sm:py-8 space-y-6 pb-28 sm:pb-12 animate-fadeIn">
      {/* Toast Alert Flotante */}
      {toast && (
        <div
          className={`fixed bottom-20 right-4 sm:bottom-6 sm:right-6 z-50 flex items-center gap-3 px-4 py-3 rounded-2xl shadow-2xl border backdrop-blur-xl animate-bounce-subtle transition ${
            toast.type === 'success'
              ? 'bg-emerald-950/90 border-emerald-500/50 text-emerald-200'
              : 'bg-rose-950/90 border-rose-500/50 text-rose-200'
          }`}
        >
          {toast.type === 'success' ? (
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
          ) : (
            <AlertTriangle className="w-5 h-5 text-rose-400 shrink-0" />
          )}
          <span className="text-xs sm:text-sm font-bold">{toast.message}</span>
        </div>
      )}

      {/* HEADER / HERO BANNER */}
      <div className="bg-gradient-to-r from-marine-900 via-marine-900/95 to-cyan-950/40 border border-marine-800 rounded-3xl p-5 sm:p-7 shadow-xl relative overflow-hidden">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 relative z-10">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-black uppercase tracking-wider px-2.5 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-400/40 flex items-center gap-1.5 shadow-neon-cyan">
                <ShieldCheck className="w-3.5 h-3.5 text-cyan-400" />
                {t('admin.adminBadge')}
              </span>
              <span className="text-xs text-slate-400 font-mono">
                {user?.email}
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
              {t('admin.title')}
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 max-w-2xl">
              {t('admin.subtitle')}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => {
                triggerHaptic();
                if (onBackToDashboard) onBackToDashboard();
              }}
              className="px-4 py-2.5 rounded-2xl bg-marine-950 border border-marine-700 text-slate-300 hover:text-white hover:border-cyan-400/80 font-bold text-xs sm:text-sm flex items-center gap-2 transition active:scale-95"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>{t('admin.backToDashboard')}</span>
            </button>
            <button
              onClick={() => {
                triggerHaptic();
                loadUsers();
              }}
              disabled={loading}
              className="min-h-[42px] px-3.5 rounded-2xl bg-cyan-500/10 border border-cyan-500/40 hover:bg-cyan-500/20 text-cyan-300 font-bold text-xs sm:text-sm flex items-center gap-2 transition active:scale-95 disabled:opacity-50"
              title={t('admin.filters.refresh')}
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">{t('admin.filters.refresh')}</span>
            </button>
          </div>
        </div>
      </div>

      {/* METRIC KPI CARDS */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        {/* Total Users */}
        <div className="bg-marine-900/90 border border-marine-800/90 rounded-2xl p-4 shadow-lg flex items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 flex items-center justify-center shrink-0">
            <Users className="w-6 h-6" />
          </div>
          <div>
            <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
              {t('admin.stats.totalUsers')}
            </p>
            <p className="text-2xl font-black text-white mt-0.5">
              {stats.total}
            </p>
          </div>
        </div>

        {/* Active Accounts */}
        <div className="bg-marine-900/90 border border-marine-800/90 rounded-2xl p-4 shadow-lg flex items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 flex items-center justify-center shrink-0">
            <UserCheck className="w-6 h-6" />
          </div>
          <div>
            <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
              {t('admin.stats.activeUsers')}
            </p>
            <p className="text-2xl font-black text-emerald-400 mt-0.5">
              {stats.active}
            </p>
          </div>
        </div>

        {/* Premium Tiers */}
        <div className="bg-marine-900/90 border border-marine-800/90 rounded-2xl p-4 shadow-lg flex items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-purple-500/15 text-purple-300 border border-purple-500/30 flex items-center justify-center shrink-0">
            <Crown className="w-6 h-6" />
          </div>
          <div>
            <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
              {t('admin.stats.premiumUsers')}
            </p>
            <p className="text-2xl font-black text-purple-300 mt-0.5">
              {stats.premium}
            </p>
          </div>
        </div>

        {/* Tanks & Measurements */}
        <div className="bg-marine-900/90 border border-marine-800/90 rounded-2xl p-4 shadow-lg flex items-center gap-3">
          <div className="w-12 h-12 rounded-2xl bg-sky-500/15 text-sky-300 border border-sky-500/30 flex items-center justify-center shrink-0">
            <Droplets className="w-6 h-6" />
          </div>
          <div>
            <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
              {t('admin.stats.totalTanks')}
            </p>
            <p className="text-2xl font-black text-white mt-0.5">
              {stats.tanks}{' '}
              <span className="text-xs font-semibold text-slate-400">
                ({stats.measurements} tests)
              </span>
            </p>
          </div>
        </div>
      </div>

      {/* FILTROS Y CONTROLES */}
      <div className="bg-marine-900/80 border border-marine-800/90 rounded-2xl p-4 shadow-md flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between">
        {/* Input de Búsqueda */}
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3.5 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t('admin.filters.searchPlaceholder')}
            className="w-full min-h-[44px] bg-marine-950 border border-marine-700 rounded-xl pl-10 pr-4 text-xs sm:text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 focus:border-cyan-400 transition"
          />
        </div>

        {/* Selectores de Plan y Estado */}
        <div className="flex items-center gap-2 flex-wrap sm:flex-nowrap">
          {/* Plan Selector */}
          <select
            value={tierFilter}
            onChange={(e) => {
              triggerHaptic();
              setTierFilter(e.target.value);
            }}
            className="min-h-[44px] bg-marine-950 border border-marine-700 text-slate-200 text-xs sm:text-sm rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 cursor-pointer transition font-medium"
          >
            <option value="all">{t('admin.filters.allPlans')}</option>
            <option value="free">{t('admin.filters.freePlan')}</option>
            <option value="premium">{t('admin.filters.premiumPlan')}</option>
          </select>

          {/* Status Selector */}
          <select
            value={statusFilter}
            onChange={(e) => {
              triggerHaptic();
              setStatusFilter(e.target.value);
            }}
            className="min-h-[44px] bg-marine-950 border border-marine-700 text-slate-200 text-xs sm:text-sm rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500/40 cursor-pointer transition font-medium"
          >
            <option value="all">{t('admin.filters.allStatuses')}</option>
            <option value="active">{t('admin.filters.activeOnly')}</option>
            <option value="suspended">{t('admin.filters.suspendedOnly')}</option>
          </select>
        </div>
      </div>

      {/* TABLA DE USUARIOS */}
      <div className="bg-marine-900/90 border border-marine-800 rounded-3xl shadow-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-marine-800 bg-marine-950/60 text-[11px] font-black text-slate-400 uppercase tracking-wider">
                <th className="py-4 px-4 sm:px-6">{t('admin.table.user')}</th>
                <th className="py-4 px-3">{t('admin.table.role')}</th>
                <th className="py-4 px-3">{t('admin.table.plan')}</th>
                <th className="py-4 px-3">{t('admin.table.tanks')}</th>
                <th className="py-4 px-3">{t('admin.table.status')}</th>
                <th className="py-4 px-4 sm:px-6 text-right">{t('admin.table.actions')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-marine-800/60 text-xs sm:text-sm">
              {filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan="6" className="py-12 text-center text-slate-400">
                    <UserX className="w-10 h-10 mx-auto text-slate-500 mb-2 opacity-60" />
                    <p className="font-bold text-white text-base">{t('admin.table.emptyTitle')}</p>
                    <p className="text-xs text-slate-500 max-w-sm mx-auto mt-1">
                      {t('admin.table.emptyDesc')}
                    </p>
                  </td>
                </tr>
              ) : (
                filteredUsers.map((u) => {
                  const isCurrent = u.id === user?.id;
                  const initials = (u.full_name || u.email || 'U')
                    .split(' ')
                    .map((n) => n[0])
                    .join('')
                    .slice(0, 2)
                    .toUpperCase();

                  const isRowLoading = actionUserId === u.id;

                  return (
                    <tr
                      key={u.id}
                      className={`hover:bg-marine-850/50 transition-colors ${
                        !u.is_active ? 'opacity-60 bg-rose-950/10' : ''
                      } ${isCurrent ? 'bg-cyan-950/20' : ''}`}
                    >
                      {/* Usuario */}
                      <td className="py-4 px-4 sm:px-6">
                        <div className="flex items-center gap-3">
                          <div
                            className={`w-10 h-10 rounded-2xl flex items-center justify-center font-black text-xs shrink-0 shadow-inner ${
                              u.is_admin
                                ? 'bg-gradient-to-tr from-amber-500 to-cyan-400 text-marine-950'
                                : 'bg-marine-800 text-cyan-300 border border-marine-700'
                            }`}
                          >
                            {initials}
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-extrabold text-white">
                                {u.full_name || u.email.split('@')[0]}
                              </span>
                              {isCurrent && (
                                <span className="text-[10px] font-black uppercase px-2 py-0.2 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-400/50">
                                  TÚ
                                </span>
                              )}
                            </div>
                            <div className="text-xs text-slate-400 flex items-center gap-2 mt-0.5">
                              <span>{u.email}</span>
                              <span className="text-slate-600">•</span>
                              <span className="text-slate-500 text-[11px]">
                                {t('admin.table.joined')}: {formatDate(u.created_at)}
                              </span>
                            </div>
                          </div>
                        </div>
                      </td>

                      {/* Rol */}
                      <td className="py-4 px-3">
                        {u.is_admin ? (
                          <span className="text-[11px] font-black uppercase tracking-wider px-2.5 py-1 rounded-xl bg-amber-500/20 text-amber-300 border border-amber-500/40 inline-flex items-center gap-1 shadow-neon-amber">
                            <ShieldCheck className="w-3.5 h-3.5 text-amber-400" />
                            {t('admin.table.adminRole')}
                          </span>
                        ) : (
                          <span className="text-[11px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-lg bg-marine-800 text-slate-400 border border-marine-700 inline-block">
                            {t('admin.table.userRole')}
                          </span>
                        )}
                      </td>

                      {/* Plan Freemium */}
                      <td className="py-4 px-3">
                        <div className="flex items-center gap-2">
                          {u.subscription_tier === 'premium' ? (
                            <span className="text-[11px] font-black uppercase tracking-wider px-2.5 py-1 rounded-xl bg-purple-500/20 text-purple-300 border border-purple-500/40 inline-flex items-center gap-1">
                              <Crown className="w-3 h-3 text-purple-300" />
                              PREMIUM
                            </span>
                          ) : (
                            <span className="text-[11px] font-black uppercase tracking-wider px-2 py-0.5 rounded-lg bg-marine-800 text-slate-300 border border-marine-700 inline-block">
                              FREE
                            </span>
                          )}

                          {/* Botón rápido de cambio de plan */}
                          <button
                            type="button"
                            onClick={() => handleToggleTier(u)}
                            disabled={isRowLoading}
                            title={
                              u.subscription_tier === 'premium'
                                ? t('admin.actions.setFree')
                                : t('admin.actions.setPremium')
                            }
                            className="p-1.5 rounded-lg bg-marine-800 hover:bg-marine-700 text-slate-400 hover:text-cyan-300 border border-marine-700 transition active:scale-95 disabled:opacity-40"
                          >
                            <Sparkles className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>

                      {/* Acuarios & Mediciones */}
                      <td className="py-4 px-3">
                        <div className="flex items-center gap-3">
                          <span className="flex items-center gap-1 text-slate-300 font-bold" title="Acuarios registrados">
                            <Droplets className="w-3.5 h-3.5 text-cyan-400" />
                            {u.tank_count || 0}
                          </span>
                          <span className="flex items-center gap-1 text-slate-400 text-xs" title="Mediciones registradas">
                            <Activity className="w-3.5 h-3.5 text-slate-500" />
                            {u.measurement_count || 0}
                          </span>
                        </div>
                      </td>

                      {/* Estado */}
                      <td className="py-4 px-3">
                        {u.is_active ? (
                          <span className="text-[11px] font-black uppercase tracking-wider px-2.5 py-1 rounded-xl bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 inline-flex items-center gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                            {t('admin.table.activeStatus')}
                          </span>
                        ) : (
                          <span className="text-[11px] font-black uppercase tracking-wider px-2.5 py-1 rounded-xl bg-rose-500/20 text-rose-300 border border-rose-500/30 inline-flex items-center gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
                            {t('admin.table.suspendedStatus')}
                          </span>
                        )}
                      </td>

                      {/* Acciones */}
                      <td className="py-4 px-4 sm:px-6 text-right">
                        <div className="flex items-center justify-end gap-2">
                          {/* Botón Suspender / Reactivar */}
                          <button
                            type="button"
                            onClick={() => handleToggleActive(u)}
                            disabled={isCurrent || isRowLoading}
                            title={
                              isCurrent
                                ? t('admin.actions.selfProtect')
                                : u.is_active
                                ? t('admin.actions.suspend')
                                : t('admin.actions.activate')
                            }
                            className={`min-h-[34px] px-3 rounded-xl font-bold text-xs flex items-center gap-1.5 transition active:scale-95 ${
                              isCurrent
                                ? 'bg-marine-800 text-slate-600 border border-marine-700/50 cursor-not-allowed opacity-40'
                                : u.is_active
                                ? 'bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/30 hover:border-amber-500/60'
                                : 'bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 hover:border-emerald-500/60'
                            }`}
                          >
                            {u.is_active ? (
                              <>
                                <UserX className="w-3.5 h-3.5" />
                                <span className="hidden sm:inline">{t('admin.actions.suspend')}</span>
                              </>
                            ) : (
                              <>
                                <UserCheck className="w-3.5 h-3.5" />
                                <span className="hidden sm:inline">{t('admin.actions.activate')}</span>
                              </>
                            )}
                          </button>

                          {/* Botón Eliminar */}
                          <button
                            type="button"
                            onClick={() => {
                              triggerHaptic();
                              setUserToDelete(u);
                            }}
                            disabled={isCurrent || isRowLoading}
                            title={isCurrent ? t('admin.actions.selfProtect') : t('admin.actions.delete')}
                            className={`w-9 h-9 rounded-xl flex items-center justify-center transition active:scale-95 ${
                              isCurrent
                                ? 'bg-marine-800 text-slate-600 border border-marine-700/50 cursor-not-allowed opacity-40'
                                : 'bg-rose-500/10 hover:bg-rose-500/25 text-rose-300 border border-rose-500/30 hover:border-rose-500/60'
                            }`}
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* MODAL DE CONFIRMACIÓN DE ELIMINACIÓN */}
      {userToDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-marine-950/80 backdrop-blur-md animate-fadeIn">
          <div className="bg-marine-900 border border-rose-500/40 rounded-3xl p-6 sm:p-8 max-w-md w-full shadow-2xl relative">
            <div className="w-14 h-14 rounded-2xl bg-rose-500/15 text-rose-400 border border-rose-500/30 flex items-center justify-center mx-auto mb-4">
              <AlertTriangle className="w-7 h-7" />
            </div>

            <h3 className="text-xl font-black text-white text-center mb-2">
              {t('admin.actions.confirmDeleteTitle')}
            </h3>

            <p className="text-xs sm:text-sm text-slate-300 text-center mb-6 leading-relaxed">
              {t('admin.actions.confirmDeleteMsg', { email: userToDelete.email })}
            </p>

            <div className="flex gap-3 justify-end">
              <button
                type="button"
                onClick={() => setUserToDelete(null)}
                className="flex-1 py-3 rounded-2xl bg-marine-950 border border-marine-700 text-slate-300 font-bold text-xs sm:text-sm hover:border-slate-500 transition active:scale-95"
              >
                {t('common.cancel')}
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                disabled={actionUserId === userToDelete.id}
                className="flex-1 py-3 rounded-2xl bg-gradient-to-r from-rose-600 to-rose-500 text-white font-black text-xs sm:text-sm shadow-neon-rose hover:brightness-110 transition active:scale-95 disabled:opacity-50"
              >
                {actionUserId === userToDelete.id ? t('common.loading') : t('admin.actions.delete')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
