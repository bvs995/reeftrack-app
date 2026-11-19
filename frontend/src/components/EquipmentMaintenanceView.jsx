import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Wrench,
  CheckCircle2,
  AlertCircle,
  Clock,
  Plus,
  Sliders,
  SlidersHorizontal,
  Pencil,
  Trash2,
  Sparkles,
  ShieldAlert,
  Layers,
  FlaskConical,
  Gauge,
  Check,
  Eye,
  EyeOff,
  X
} from 'lucide-react';
import {
  fetchMaintenanceTasks,
  completeMaintenanceTask,
  createMaintenanceTask,
  updateMaintenanceTask,
  deleteMaintenanceTask
} from '../api';

export default function EquipmentMaintenanceView({ tank, onTaskUpdated }) {
  const { t } = useTranslation();
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showDisabled, setShowDisabled] = useState(false);
  const [completingId, setCompletingId] = useState(null);

  // Modales
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingTask, setEditingTask] = useState(null);

  // Formulario de nueva tarea
  const [newTitle, setNewTitle] = useState('');
  const [newCategory, setNewCategory] = useState('mechanical');
  const [newFrequency, setNewFrequency] = useState(7);
  const [newNotes, setNewNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Formulario de edición
  const [editTitle, setEditTitle] = useState('');
  const [editCategory, setEditCategory] = useState('mechanical');
  const [editFrequency, setEditFrequency] = useState(7);
  const [editEnabled, setEditEnabled] = useState(true);
  const [editNotes, setEditNotes] = useState('');

  const triggerHaptic = (ms = 20) => {
    if (typeof navigator !== 'undefined' && navigator.vibrate) {
      navigator.vibrate(ms);
    }
  };

  useEffect(() => {
    if (tank?.id) {
      loadTasks();
    }
  }, [tank?.id]);

  const loadTasks = async () => {
    setLoading(true);
    try {
      const data = await fetchMaintenanceTasks(tank.id, true);
      setTasks(data || []);
    } catch (err) {
      console.error('Error al cargar tareas de mantenimiento:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleComplete = async (taskId) => {
    triggerHaptic(30);
    setCompletingId(taskId);
    try {
      const updated = await completeMaintenanceTask(taskId);
      setTasks(prev => prev.map(t => (t.id === taskId ? updated : t)));
      triggerHaptic([30, 50, 80]);
      if (onTaskUpdated) onTaskUpdated();
    } catch (err) {
      alert(err.message || 'Error al completar tarea');
    } finally {
      setCompletingId(null);
    }
  };

  const handleCreateTask = async (e) => {
    e.preventDefault();
    if (!newTitle.trim()) return;

    setSubmitting(true);
    try {
      const created = await createMaintenanceTask(tank.id, {
        title: newTitle.trim(),
        category: newCategory,
        frequency_days: parseInt(newFrequency, 10) || 7,
        notes: newNotes.trim() || undefined,
        is_enabled: true
      });
      setTasks(prev => [...prev, created]);
      setShowAddModal(false);
      setNewTitle('');
      setNewNotes('');
      setNewFrequency(7);
      triggerHaptic(25);
      if (onTaskUpdated) onTaskUpdated();
    } catch (err) {
      alert(err.message || 'Error al crear tarea');
    } finally {
      setSubmitting(false);
    }
  };

  const handleOpenEdit = (task) => {
    setEditingTask(task);
    setEditTitle(task.title);
    setEditCategory(task.category || 'mechanical');
    setEditFrequency(task.frequency_days || 7);
    setEditEnabled(task.is_enabled);
    setEditNotes(task.notes || '');
  };

  const handleSaveEdit = async (e) => {
    e.preventDefault();
    if (!editingTask || !editTitle.trim()) return;

    setSubmitting(true);
    try {
      const updated = await updateMaintenanceTask(editingTask.id, {
        title: editTitle.trim(),
        category: editCategory,
        frequency_days: parseInt(editFrequency, 10) || 7,
        is_enabled: editEnabled,
        notes: editNotes.trim() || undefined
      });
      setTasks(prev => prev.map(t => (t.id === editingTask.id ? updated : t)));
      setEditingTask(null);
      triggerHaptic(25);
      if (onTaskUpdated) onTaskUpdated();
    } catch (err) {
      alert(err.message || 'Error al actualizar tarea');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (taskId) => {
    if (!window.confirm('¿Estás seguro de eliminar esta tarea de mantenimiento?')) return;
    try {
      await deleteMaintenanceTask(taskId);
      setTasks(prev => prev.filter(t => t.id !== taskId));
      setEditingTask(null);
      triggerHaptic(25);
      if (onTaskUpdated) onTaskUpdated();
    } catch (err) {
      alert(err.message || 'Error al eliminar tarea');
    }
  };

  const getCategoryMeta = (cat) => {
    switch (cat) {
      case 'mechanical':
        return {
          label: t('maintenance.categories.mechanical') || 'Mecánica',
          icon: Layers,
          color: 'text-cyan-400 bg-cyan-500/10 border-cyan-500/30'
        };
      case 'equipment':
        return {
          label: t('maintenance.categories.equipment') || 'Equipo / Bombas',
          icon: Wrench,
          color: 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30'
        };
      case 'chemical':
        return {
          label: t('maintenance.categories.chemical') || 'Química / Resinas',
          icon: FlaskConical,
          color: 'text-purple-400 bg-purple-500/10 border-purple-500/30'
        };
      case 'calibration':
        return {
          label: t('maintenance.categories.calibration') || 'Calibración',
          icon: Gauge,
          color: 'text-amber-400 bg-amber-500/10 border-amber-500/30'
        };
      default:
        return {
          label: cat || 'General',
          icon: Sparkles,
          color: 'text-slate-400 bg-slate-500/10 border-slate-500/30'
        };
    }
  };

  const visibleTasks = tasks.filter(t => (showDisabled ? true : t.is_enabled));
  const overdueCount = tasks.filter(t => t.is_enabled && t.status === 'overdue').length;
  const dueSoonCount = tasks.filter(t => t.is_enabled && t.status === 'due_soon').length;
  const activeCount = tasks.filter(t => t.is_enabled).length;

  return (
    <div className="space-y-6">
      {/* Barra de métricas y acciones rápidas */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 p-4 rounded-2xl bg-slate-900/80 border border-cyan-500/30 backdrop-blur-md shadow-lg">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center text-cyan-400 shrink-0">
            <Wrench className="w-5 h-5 stroke-[2.2]" />
          </div>
          <div>
            <h3 className="text-sm font-black text-white flex items-center gap-2">
              <span>{t('maintenance.tabEquipment') || 'Equipo y Limpieza'}</span>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-300 border border-cyan-500/30">
                {activeCount} activas
              </span>
            </h3>
            <p className="text-xs text-slate-400">
              {overdueCount > 0 ? (
                <span className="text-coral-400 font-bold">
                  ⚠️ {overdueCount} tareas vencidas requieren atención inmediata
                </span>
              ) : dueSoonCount > 0 ? (
                <span className="text-amber-300 font-bold">
                  ⏰ {dueSoonCount} tareas próximas a vencer
                </span>
              ) : (
                <span className="text-emerald-400 font-semibold">
                  ✓ Todos los mantenimientos están al día
                </span>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5 shrink-0">
          <button
            type="button"
            onClick={() => setShowDisabled(!showDisabled)}
            className={`btn-touch px-3 py-2 text-xs font-bold rounded-xl border transition-colors flex items-center gap-1.5 ${
              showDisabled
                ? 'bg-slate-800 text-cyan-300 border-cyan-500/40'
                : 'bg-slate-950/60 text-slate-400 border-slate-700 hover:text-slate-200'
            }`}
            title="Alternar tareas inactivas"
          >
            {showDisabled ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
            <span className="hidden sm:inline">
              {showDisabled
                ? t('maintenance.hideDisabled') || 'Ocultar inactivas'
                : t('maintenance.showDisabled') || 'Ver inactivas'}
            </span>
          </button>

          <button
            type="button"
            onClick={() => setShowAddModal(true)}
            className="btn-touch px-4 py-2 bg-gradient-to-r from-cyan-500 via-cyan-400 to-emerald-400 hover:from-cyan-400 hover:to-emerald-300 text-marine-950 font-black text-xs rounded-xl shadow-neon-cyan flex items-center gap-1.5 active:scale-95 transition-all"
          >
            <Plus className="w-4 h-4 stroke-[2.5]" />
            <span>{t('maintenance.addTask') || 'Nueva Tarea'}</span>
          </button>
        </div>
      </div>

      {/* Grid de Tareas de Mantenimiento */}
      {loading ? (
        <div className="p-12 text-center text-slate-400 space-y-2">
          <div className="w-8 h-8 mx-auto border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
          <p className="text-xs font-semibold">Cargando protocolo de mantenimiento...</p>
        </div>
      ) : visibleTasks.length === 0 ? (
        <div className="p-12 text-center rounded-2xl bg-slate-900/40 border border-slate-800 text-slate-400 space-y-3">
          <Wrench className="w-10 h-10 mx-auto text-slate-600" />
          <p className="text-sm font-semibold text-slate-300">No hay tareas de mantenimiento configuradas.</p>
          <button
            onClick={() => setShowAddModal(true)}
            className="px-4 py-2 bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 rounded-xl text-xs font-bold hover:bg-cyan-500/30"
          >
            + Crear primera tarea
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {visibleTasks.map((task) => {
            const cat = getCategoryMeta(task.category);
            const CatIcon = cat.icon;
            const isOverdue = task.is_enabled && task.status === 'overdue';
            const isDueSoon = task.is_enabled && task.status === 'due_soon';
            const isCompleting = completingId === task.id;

            // Cálculo visual de barra de progreso de ciclo
            let pct = 0;
            if (task.days_since_last !== null && task.frequency_days > 0) {
              pct = Math.min(100, Math.round((task.days_since_last / task.frequency_days) * 100));
            } else if (task.days_until_due !== null && task.frequency_days > 0) {
              const elapsed = task.frequency_days - task.days_until_due;
              pct = Math.min(100, Math.max(0, Math.round((elapsed / task.frequency_days) * 100)));
            }

            return (
              <div
                key={task.id}
                className={`rounded-2xl p-4 transition-all flex flex-col justify-between border ${
                  !task.is_enabled
                    ? 'bg-slate-950/40 border-slate-800/60 opacity-60'
                    : isOverdue
                    ? 'bg-gradient-to-br from-coral-950/40 via-slate-900/90 to-slate-900/90 border-coral-500/60 shadow-[0_0_15px_rgba(244,63,94,0.15)] ring-1 ring-coral-500/30'
                    : isDueSoon
                    ? 'bg-gradient-to-br from-amber-950/30 via-slate-900/90 to-slate-900/90 border-amber-500/50 shadow-[0_0_12px_rgba(245,158,11,0.12)]'
                    : 'bg-slate-900/80 border-cyan-500/25 hover:border-cyan-500/50'
                }`}
              >
                <div>
                  {/* Encabezado: Categoría y Estado */}
                  <div className="flex items-center justify-between gap-2 mb-2.5">
                    <span className={`text-[10px] font-extrabold px-2 py-0.5 rounded-full border flex items-center gap-1 ${cat.color}`}>
                      <CatIcon className="w-3 h-3" />
                      <span>{cat.label}</span>
                    </span>

                    <div className="flex items-center gap-1.5">
                      {!task.is_enabled ? (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
                          {t('maintenance.inactive') || 'Inactiva'}
                        </span>
                      ) : isOverdue ? (
                        <span className="text-[10px] font-black px-2 py-0.5 rounded-full bg-coral-500/20 text-coral-300 border border-coral-500/40 flex items-center gap-1 animate-pulse">
                          <AlertCircle className="w-3 h-3" />
                          <span>
                            {task.days_until_due < 0
                              ? `Vencida hace ${Math.abs(task.days_until_due)}d`
                              : 'Vence hoy'}
                          </span>
                        </span>
                      ) : isDueSoon ? (
                        <span className="text-[10px] font-extrabold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/40 flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          <span>{task.days_until_due <= 0 ? 'Vence hoy' : 'Próxima en 1d'}</span>
                        </span>
                      ) : task.status === 'pending' ? (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-300 border border-cyan-500/30">
                          {t('maintenance.pending') || 'Pendiente'}
                        </span>
                      ) : (
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                          <CheckCircle2 className="w-3 h-3" />
                          <span>{`En ${task.days_until_due}d`}</span>
                        </span>
                      )}

                      <button
                        type="button"
                        onClick={() => handleOpenEdit(task)}
                        className="p-1 rounded text-slate-400 hover:text-cyan-300 hover:bg-slate-800 transition-colors"
                        title={t('maintenance.editTask') || 'Editar tarea'}
                      >
                        <Pencil className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Título de la tarea */}
                  <h4 className="text-sm font-black text-white tracking-wide mb-1">
                    {task.title}
                  </h4>

                  {/* Notas o descripción breve */}
                  {task.notes && (
                    <p className="text-xs text-slate-400 line-clamp-2 mb-3">
                      {task.notes}
                    </p>
                  )}

                  {/* Barra de progreso de ciclo */}
                  {task.is_enabled && (
                    <div className="mt-3 mb-2 space-y-1">
                      <div className="flex items-center justify-between text-[10px] text-slate-400 font-semibold">
                        <span>
                          {task.days_since_last !== null
                            ? `Hace ${task.days_since_last} días`
                            : 'Sin registro previo'}
                        </span>
                        <span>Cada {task.frequency_days} días</span>
                      </div>
                      <div className="w-full h-1.5 rounded-full bg-slate-950 overflow-hidden border border-slate-800">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${
                            isOverdue
                              ? 'bg-gradient-to-r from-coral-500 to-rose-400 w-full'
                              : isDueSoon
                              ? 'bg-gradient-to-r from-amber-500 to-amber-300'
                              : 'bg-gradient-to-r from-cyan-500 to-emerald-400'
                          }`}
                          style={{ width: isOverdue ? '100%' : `${pct}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>

                {/* Pie de tarjeta con botón de 1 toque */}
                <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between gap-3">
                  <div className="text-[11px] text-slate-400">
                    <span className="text-slate-500">Próxima: </span>
                    <span className="font-bold text-slate-300">
                      {task.next_due_at
                        ? new Date(task.next_due_at).toLocaleDateString(undefined, {
                            day: 'numeric',
                            month: 'short'
                          })
                        : '—'}
                    </span>
                  </div>

                  <button
                    type="button"
                    onClick={() => handleComplete(task.id)}
                    disabled={isCompleting || !task.is_enabled}
                    className={`btn-touch px-4 py-2 rounded-xl text-xs font-black flex items-center gap-1.5 transition-all active:scale-95 ${
                      !task.is_enabled
                        ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                        : isOverdue
                        ? 'bg-gradient-to-r from-coral-500 via-rose-400 to-coral-500 text-white shadow-neon-coral'
                        : 'bg-gradient-to-r from-cyan-500 via-cyan-400 to-emerald-400 text-marine-950 shadow-neon-cyan hover:brightness-110'
                    }`}
                  >
                    {isCompleting ? (
                      <div className="w-3.5 h-3.5 border-2 border-marine-950 border-t-transparent rounded-full animate-spin" />
                    ) : (
                      <Check className="w-4 h-4 stroke-[3]" />
                    )}
                    <span>{t('maintenance.doneToday') || 'Listo hoy'}</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Modal: Agregar Tarea Personalizada */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-marine-950/80 backdrop-blur-md animate-in fade-in">
          <div className="relative w-full max-w-md bg-slate-900 border border-cyan-500/30 rounded-3xl p-6 shadow-2xl space-y-5">
            <div className="flex items-center justify-between border-b border-cyan-500/20 pb-3">
              <div className="flex items-center gap-2">
                <Wrench className="w-5 h-5 text-cyan-400" />
                <h3 className="text-base font-black text-white">
                  {t('maintenance.customTaskTitle') || 'Nueva Tarea de Mantenimiento'}
                </h3>
              </div>
              <button
                onClick={() => setShowAddModal(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateTask} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-cyan-300 uppercase tracking-wider mb-1.5">
                  {t('maintenance.taskName') || 'Nombre de la tarea'} *
                </label>
                <input
                  type="text"
                  required
                  placeholder="ej. Limpieza de sonda de temperatura"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-cyan-500/30 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400 font-semibold"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-cyan-300 uppercase tracking-wider mb-1.5">
                    {t('maintenance.category') || 'Categoría'}
                  </label>
                  <select
                    value={newCategory}
                    onChange={(e) => setNewCategory(e.target.value)}
                    className="w-full px-3 py-2.5 rounded-xl bg-slate-950 border border-cyan-500/30 text-white font-semibold focus:outline-none focus:border-cyan-400 text-xs"
                  >
                    <option value="mechanical">Filtración Mecánica</option>
                    <option value="equipment">Equipo / Bombas</option>
                    <option value="chemical">Química / Resinas</option>
                    <option value="calibration">Calibración</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-cyan-300 uppercase tracking-wider mb-1.5">
                    {t('maintenance.frequency') || 'Frecuencia (días)'} *
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="365"
                    required
                    value={newFrequency}
                    onChange={(e) => setNewFrequency(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-cyan-500/30 text-white font-bold focus:outline-none focus:border-cyan-400"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-cyan-300 uppercase tracking-wider mb-1.5">
                  {t('maintenance.notes') || 'Instrucciones o notas'}
                </label>
                <textarea
                  rows="2"
                  placeholder="Detalles sobre cómo ejecutar o limpiar el componente..."
                  value={newNotes}
                  onChange={(e) => setNewNotes(e.target.value)}
                  className="w-full px-3.5 py-2 rounded-xl bg-slate-950 border border-cyan-500/30 text-white placeholder-slate-500 focus:outline-none focus:border-cyan-400 text-xs"
                />
              </div>

              <div className="flex items-center justify-end gap-2.5 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2.5 rounded-xl text-slate-300 hover:bg-slate-800 text-xs font-bold"
                >
                  {t('common.cancel') || 'Cancelar'}
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-cyan-400 text-marine-950 text-xs font-black shadow-neon-cyan active:scale-95 disabled:opacity-50"
                >
                  {submitting ? 'Guardando...' : 'Crear Tarea'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Editar Tarea */}
      {editingTask && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-marine-950/80 backdrop-blur-md animate-in fade-in">
          <div className="relative w-full max-w-md bg-slate-900 border border-cyan-500/30 rounded-3xl p-6 shadow-2xl space-y-5">
            <div className="flex items-center justify-between border-b border-cyan-500/20 pb-3">
              <div className="flex items-center gap-2">
                <Pencil className="w-5 h-5 text-cyan-400" />
                <h3 className="text-base font-black text-white">
                  {t('maintenance.editTask') || 'Editar Tarea de Mantenimiento'}
                </h3>
              </div>
              <button
                onClick={() => setEditingTask(null)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSaveEdit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-cyan-300 uppercase tracking-wider mb-1.5">
                  {t('maintenance.taskName') || 'Nombre de la tarea'} *
                </label>
                <input
                  type="text"
                  required
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-cyan-500/30 text-white font-semibold focus:outline-none focus:border-cyan-400"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-bold text-cyan-300 uppercase tracking-wider mb-1.5">
                    {t('maintenance.category') || 'Categoría'}
                  </label>
                  <select
                    value={editCategory}
                    onChange={(e) => setEditCategory(e.target.value)}
                    className="w-full px-3 py-2.5 rounded-xl bg-slate-950 border border-cyan-500/30 text-white font-semibold focus:outline-none focus:border-cyan-400 text-xs"
                  >
                    <option value="mechanical">Filtración Mecánica</option>
                    <option value="equipment">Equipo / Bombas</option>
                    <option value="chemical">Química / Resinas</option>
                    <option value="calibration">Calibración</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-cyan-300 uppercase tracking-wider mb-1.5">
                    {t('maintenance.frequency') || 'Frecuencia (días)'} *
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="365"
                    required
                    value={editFrequency}
                    onChange={(e) => setEditFrequency(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-cyan-500/30 text-white font-bold focus:outline-none focus:border-cyan-400"
                  />
                </div>
              </div>

              {/* Toggle Habilitada / Inactiva */}
              <div className="flex items-center justify-between p-3 rounded-xl bg-slate-950/80 border border-slate-800">
                <div>
                  <div className="text-xs font-bold text-white">Estado de la tarea</div>
                  <div className="text-[11px] text-slate-400">
                    {editEnabled ? 'Activa y enviando alertas de vencimiento' : 'Desactivada (no genera alertas)'}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setEditEnabled(!editEnabled)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-extrabold border transition-colors ${
                    editEnabled
                      ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
                      : 'bg-slate-800 text-slate-400 border-slate-700'
                  }`}
                >
                  {editEnabled ? 'Habilitada' : 'Inactiva'}
                </button>
              </div>

              <div>
                <label className="block text-xs font-bold text-cyan-300 uppercase tracking-wider mb-1.5">
                  {t('maintenance.notes') || 'Instrucciones o notas'}
                </label>
                <textarea
                  rows="2"
                  value={editNotes}
                  onChange={(e) => setEditNotes(e.target.value)}
                  className="w-full px-3.5 py-2 rounded-xl bg-slate-950 border border-cyan-500/30 text-white focus:outline-none focus:border-cyan-400 text-xs"
                />
              </div>

              <div className="flex items-center justify-between gap-2.5 pt-2">
                {editingTask.task_key === 'custom' ? (
                  <button
                    type="button"
                    onClick={() => handleDelete(editingTask.id)}
                    className="px-3 py-2 text-coral-400 hover:bg-coral-500/10 rounded-xl text-xs font-bold flex items-center gap-1 border border-coral-500/20"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Eliminar</span>
                  </button>
                ) : <div />}

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setEditingTask(null)}
                    className="px-4 py-2 rounded-xl text-slate-300 hover:bg-slate-800 text-xs font-bold"
                  >
                    {t('common.cancel') || 'Cancelar'}
                  </button>
                  <button
                    type="submit"
                    disabled={submitting}
                    className="px-5 py-2 rounded-xl bg-gradient-to-r from-cyan-500 to-cyan-400 text-marine-950 text-xs font-black shadow-neon-cyan active:scale-95 disabled:opacity-50"
                  >
                    {submitting ? 'Guardando...' : 'Guardar Cambios'}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
