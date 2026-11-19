import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import {
  AlertTriangle,
  CheckCircle2,
  TrendingDown,
  TrendingUp,
  Droplets,
  Calendar,
  Activity,
  Plus,
  ArrowRight,
  ShieldAlert,
  Info,
  Clock,
  Sparkles,
  ChevronDown,
  ChevronUp,
  SlidersHorizontal,
  Pencil,
  Wrench
} from 'lucide-react';
import QuickEntryForm from './QuickEntryForm';
import { updateAquariumVolume, fetchMaintenanceTasks, completeMaintenanceTask } from '../api';

export default function Dashboard({
  analytics,
  activeTank,
  loading,
  onOpenQuickLog,
  onOpenWaterChange,
  onOpenEditTankModal,
  onSelectTab,
  onSelectParameterForChart,
  onMeasurementSaved
}) {
  const { t } = useTranslation();
  const [showInlineForm, setShowInlineForm] = useState(false);
  const [overdueTasks, setOverdueTasks] = useState([]);
  const [completingTaskId, setCompletingTaskId] = useState(null);

  const triggerHaptic = () => {
    if (typeof navigator !== 'undefined' && navigator.vibrate) {
      navigator.vibrate(15);
    }
  };

  const tankId = activeTank?.id || analytics?.tank_id || analytics?.id;

  useEffect(() => {
    let isMounted = true;
    const loadOverdue = async () => {
      if (!tankId) return;
      try {
        const data = await fetchMaintenanceTasks(tankId, false);
        if (isMounted && Array.isArray(data)) {
          setOverdueTasks(data.filter(t => t.is_enabled && t.status === 'overdue'));
        }
      } catch (err) {
        // Silencioso
      }
    };
    loadOverdue();
    return () => { isMounted = false; };
  }, [tankId]);

  const handleQuickCompleteTask = async (taskId) => {
    triggerHaptic(30);
    setCompletingTaskId(taskId);
    try {
      await completeMaintenanceTask(taskId);
      setOverdueTasks(prev => prev.filter(t => t.id !== taskId));
      if (onMeasurementSaved) onMeasurementSaved();
    } catch (err) {
      console.error(err);
    } finally {
      setCompletingTaskId(null);
    }
  };

  if (loading && !analytics) {
    return (
      <div className="py-24 flex flex-col items-center justify-center text-slate-400 gap-3">
        <Activity className="w-10 h-10 animate-spin text-cyan-400 drop-shadow-[0_0_10px_rgba(6,182,212,0.8)]" />
        <p className="text-sm font-semibold tracking-wide text-slate-300">
          {t('dashboard.analyzing')}
        </p>
      </div>
    );
  }

  if (!analytics) return null;

  const {
    tank_name,
    tank_type,
    volume_liters,
    health_score,
    parameters = [],
    alerts = [],
    water_change_prediction
  } = analytics;

  const getScoreColor = (score) => {
    if (score >= 85) return 'text-emerald-400 border-emerald-500/50 bg-emerald-500/10 shadow-neon-emerald';
    if (score >= 70) return 'text-amber-400 border-amber-500/50 bg-amber-500/10';
    return 'text-coral-400 border-coral-500/50 bg-coral-500/10 shadow-neon-coral';
  };

  const getTankTypeLabel = (type) => {
    if (type === 'arrecife' || type === 'reef') return 'Arrecife (Solo Corales)';
    if (type === 'mixto' || type === 'mixed') return 'Arrecife Mixto (Corales y Peces)';
    if (type === 'peces_marinos' || type === 'marine_fish') return 'Solo Peces Marinos';
    if (type === 'plantado' || type === 'freshwater_planted') return 'Agua Dulce Plantado';
    if (type === 'dulce' || type === 'freshwater_community') return 'Agua Dulce Estándar';
    return type ? type.replace(/_/g, ' ') : t('dashboard.reefType');
  };

  const criticalParams = parameters.filter(p => p.is_critical);
  const secondaryParams = parameters.filter(p => !p.is_critical);

  const handleUpdateVolume = async (newVolume) => {
    try {
      const tankId = analytics.tank_id || analytics.id;
      await updateAquariumVolume(tankId, newVolume);
      if (onMeasurementSaved) onMeasurementSaved(); // Recarga el dashboard
    } catch (err) {
      console.error('Error al actualizar litraje:', err);
      alert(err.message || 'Error al actualizar el litraje del acuario');
    }
  };

  return (
    <div className="space-y-6 pb-28 max-w-7xl mx-auto px-3 sm:px-6 pt-4">
      {/* Banner Discreto de Mantenimiento Vencido */}
      {overdueTasks.length > 0 && (
        <div className="relative overflow-hidden rounded-2xl p-4 bg-gradient-to-r from-coral-950/80 via-marine-900/90 to-marine-950/90 border border-coral-500/40 shadow-neon-coral flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 animate-in fade-in slide-in-from-top-2 duration-300">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-coral-500/20 text-coral-400 border border-coral-500/40 flex items-center justify-center shrink-0">
              <Wrench className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-black uppercase tracking-wider text-coral-400">
                  Mantenimiento Vencido ({overdueTasks.length})
                </span>
                <span className="w-2 h-2 rounded-full bg-coral-400 animate-ping" />
              </div>
              <p className="text-xs text-slate-200 font-semibold mt-0.5">
                {overdueTasks.map(t => t.title).join(' • ')}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 self-stretch sm:self-auto justify-end">
            {overdueTasks.length === 1 && (
              <button
                type="button"
                disabled={completingTaskId === overdueTasks[0].id}
                onClick={() => handleQuickCompleteTask(overdueTasks[0].id)}
                className="px-3.5 py-2 rounded-xl bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-300 border border-cyan-500/40 text-xs font-bold transition active:scale-95 disabled:opacity-50 cursor-pointer"
              >
                {completingTaskId === overdueTasks[0].id ? 'Guardando...' : '✓ Listo hoy'}
              </button>
            )}
            <button
              type="button"
              onClick={() => {
                triggerHaptic();
                onOpenWaterChange();
              }}
              className="px-3.5 py-2 rounded-xl bg-coral-500/20 hover:bg-coral-500/30 text-coral-300 border border-coral-500/40 text-xs font-bold transition active:scale-95 whitespace-nowrap cursor-pointer"
            >
              Ir a Mantenimiento →
            </button>
          </div>
        </div>
      )}

      {/* Hero Overview Card - Slate-900 con acentos cian y azul marino */}
      <div className="relative overflow-hidden rounded-3xl glass-panel p-5 sm:p-7 border border-marine-700/80 shadow-2xl">
        <div className="absolute -right-16 -top-16 w-60 h-60 bg-cyan-500/15 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -left-16 -bottom-16 w-60 h-60 bg-emerald-500/15 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-bold px-3 py-1 rounded-full bg-marine-800 text-cyan-300 border border-cyan-500/30">
                {getTankTypeLabel(tank_type)}
              </span>
              <span className="text-xs text-slate-400 font-medium flex items-center gap-1.5">
                {t('dashboard.netVolume')} <strong className="text-white font-bold">{volume_liters} {t('common.liters')}</strong>
              </span>
              <button
                type="button"
                onClick={() => {
                  triggerHaptic();
                  const targetTank = activeTank || (analytics ? {
                    id: analytics.tank_id || analytics.id,
                    name: tank_name,
                    volume_liters: volume_liters,
                    tank_type: tank_type
                  } : null);
                  if (onOpenEditTankModal && targetTank) {
                    onOpenEditTankModal(targetTank);
                  } else {
                    const input = window.prompt("Ingresa el nuevo volumen neto del acuario en litros:", volume_liters);
                    if (input && !isNaN(input) && parseFloat(input) > 0) {
                      handleUpdateVolume(parseFloat(input));
                    }
                  }
                }}
                title="Editar Acuario / Litraje"
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-xl bg-cyan-500/15 hover:bg-cyan-500/25 text-cyan-300 border border-cyan-500/40 text-xs font-bold transition active:scale-95 shadow-sm"
              >
                <Pencil className="w-3.5 h-3.5" />
                <span>Editar Acuario / Litraje</span>
              </button>
            </div>
            <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-white">
              {tank_name}
            </h1>
            <p className="text-xs sm:text-sm text-slate-300 max-w-xl leading-relaxed">
              {t('dashboard.heroDesc')}
            </p>
          </div>

          {/* Health Score Pill */}
          <div className="flex items-center gap-4 self-stretch sm:self-auto justify-between sm:justify-start bg-marine-950/90 p-4 rounded-2xl border border-marine-700/80 shadow-inner">
            <div className="flex flex-col">
              <span className="text-[11px] font-black uppercase tracking-wider text-slate-400">
                {t('dashboard.biologicalStability')}
              </span>
              <span className="text-xs font-bold text-slate-200">
                {health_score >= 85 ? t('common.optimal') : health_score >= 70 ? t('common.warning') : t('common.danger')}
              </span>
            </div>
            <div className={`w-16 h-16 rounded-2xl border-2 flex items-center justify-center font-black text-2xl ${getScoreColor(health_score)}`}>
              {health_score}%
            </div>
          </div>
        </div>

        {/* CONTENEDOR DE BOTONES DE ACCIÓN (Agrupados) */}
        <div className="mt-6 flex flex-col gap-3">
          
          {/* Fila superior: Mediciones y Test */}
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => {
                triggerHaptic();
                setShowInlineForm(prev => !prev);
              }}
              className="flex-1 bg-slate-800 border border-slate-700 rounded-2xl p-4 flex items-center justify-center text-sm font-semibold text-white hover:bg-slate-700 transition-colors active:scale-95 cursor-pointer"
            >
              <span className="mr-2">⎚</span> {showInlineForm ? t('common.close') : 'Registrar Medición'}
            </button>
            <button
              type="button"
              onClick={() => {
                triggerHaptic();
                onOpenQuickLog();
              }}
              className="flex-1 bg-cyan-400 text-slate-900 rounded-2xl p-4 flex items-center justify-center font-bold shadow-lg shadow-cyan-500/30 hover:bg-cyan-300 transition-colors active:scale-95 cursor-pointer"
            >
              + Registrar Test Rápido
            </button>
          </div>
          
          {/* Fila inferior: Nuevo botón de Cambio de Agua centralizado */}
          <button
            type="button"
            onClick={() => {
              triggerHaptic();
              onOpenWaterChange();
            }}
            className="w-full bg-blue-900/30 border border-blue-500/50 text-blue-400 rounded-2xl p-4 flex items-center justify-center font-semibold hover:bg-blue-900/50 transition-colors active:scale-95 cursor-pointer"
          >
            <span className="mr-2">💧</span> Registrar Cambio de Agua
          </button>

        </div>
      </div>

      {/* Formulario de Entrada Rápida Desplegable */}
      {showInlineForm && (
        <div className="glass-panel rounded-3xl p-5 sm:p-7 border border-cyan-500/40 bg-marine-900/95 shadow-neon-cyan animate-in fade-in slide-in-from-top-4 duration-300">
          <div className="flex items-center justify-between pb-4 mb-4 border-b border-marine-800">
            <div>
              <h3 className="font-black text-lg text-white flex items-center gap-2">
                <SlidersHorizontal className="w-5 h-5 text-cyan-400" />
                {t('dashboard.logMeasurement')}
              </h3>
            </div>
            <button
              onClick={() => setShowInlineForm(false)}
              className="text-xs text-slate-400 hover:text-white font-bold p-1 rounded-lg"
            >
              {t('common.close')}
            </button>
          </div>

          <QuickEntryForm
            onSuccess={() => {
              if (onMeasurementSaved) onMeasurementSaved();
              setShowInlineForm(false);
            }}
            onCancel={() => setShowInlineForm(false)}
          />
        </div>
      )}

      {/* Alertas Predictivas Inteligentes */}
      {alerts.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-xs sm:text-sm font-black uppercase tracking-wider text-slate-400 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-amber-400" />
            <span>Alertas ({alerts.length})</span>
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
            {alerts.map((alert, idx) => {
              const isDanger = alert.type === 'danger';
              return (
                <div
                  key={idx}
                  className={`rounded-2xl p-4 sm:p-5 border transition-all ${
                    isDanger
                      ? 'bg-rose-950/40 border-rose-500/50 text-rose-100 shadow-neon-coral'
                      : 'bg-amber-950/40 border-amber-500/50 text-amber-100'
                  }`}
                >
                  <div className="flex items-start gap-3.5">
                    <div
                      className={`p-2.5 rounded-xl mt-0.5 ${
                        isDanger ? 'bg-rose-500/20 text-rose-400' : 'bg-amber-500/20 text-amber-400'
                      }`}
                    >
                      <AlertTriangle className="w-5 h-5 stroke-[2.5]" />
                    </div>
                    <div className="space-y-2 flex-1">
                      <div className="flex items-center justify-between gap-2">
                        <h4 className="font-extrabold text-sm sm:text-base leading-tight text-white">
                          {alert.title}
                        </h4>
                        <button
                          onClick={() => {
                            triggerHaptic();
                            if (alert.parameter) onSelectParameterForChart(alert.parameter);
                            onSelectTab('trends');
                          }}
                          className="min-h-[36px] px-2 text-xs font-bold text-cyan-400 hover:text-cyan-300 flex items-center gap-1 active:scale-95"
                        >
                          {t('trends.viewCurve')} <ArrowRight className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      <p className="text-xs text-slate-300 leading-relaxed font-medium">
                        {alert.message}
                      </p>
                      {alert.action && (
                        <div className="pt-2 flex items-start gap-2 text-xs font-semibold text-cyan-300 bg-marine-950/80 p-2.5 rounded-xl border border-marine-800">
                          <span className="text-cyan-400 font-bold shrink-0">{t('common.warning')}:</span>
                          <span>{alert.action}</span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Tarjeta de Predicción de Cambio de Agua */}
      {water_change_prediction && (
        <div className="glass-panel rounded-3xl p-5 sm:p-6 border border-cyan-500/30 bg-gradient-to-r from-marine-900 via-marine-850 to-marine-900 shadow-neon-cyan">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="flex items-start gap-4">
              <div className="p-3.5 rounded-2xl bg-cyan-500/20 text-cyan-400 border border-cyan-500/40">
                <Droplets className="w-7 h-7" />
              </div>
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-black uppercase tracking-wider text-cyan-400">
                    {t('nav.water')}
                  </span>
                  <span className="text-xs px-2.5 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-400/40 font-bold">
                    {water_change_prediction.suggested_date}
                  </span>
                </div>
                <h3 className="text-lg sm:text-xl font-black text-white">
                  {water_change_prediction.recommended_percentage}% ({water_change_prediction.recommended_liters} {t('common.liters')})
                </h3>
                <p className="text-xs text-slate-300 max-w-xl font-medium">
                  {water_change_prediction.reason}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2.5 w-full sm:w-auto">
              <button
                onClick={() => {
                  triggerHaptic();
                  onSelectTab('water');
                }}
                className="btn-touch-secondary flex-1 sm:flex-none text-xs"
              >
                {t('common.view')}
              </button>
              <button
                onClick={() => {
                  triggerHaptic();
                  onOpenWaterChange();
                }}
                className="btn-touch-primary flex-1 sm:flex-none text-xs"
              >
                {t('dashboard.logMeasurement')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Grid de Parámetros Críticos */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-xs sm:text-sm font-black uppercase tracking-wider text-slate-400 flex items-center gap-2">
            <Activity className="w-4 h-4 text-cyan-400" />
            {t('dashboard.criticalParameters')} ({criticalParams.length})
          </h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
          {criticalParams.map((param) => (
            <ParameterCard
              key={param.parameter_code}
              param={param}
              onQuickLog={() => {
                triggerHaptic();
                onOpenQuickLog(param.parameter_code);
              }}
              onViewTrend={() => {
                triggerHaptic();
                onSelectParameterForChart(param.parameter_code);
                onSelectTab('trends');
              }}
            />
          ))}
        </div>
      </div>

      {/* Grid de Parámetros Secundarios */}
      {secondaryParams.length > 0 && (
        <div className="space-y-3 pt-2">
          <div className="flex items-center justify-between">
            <h2 className="text-xs sm:text-sm font-black uppercase tracking-wider text-slate-400 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-slate-400" />
              {t('dashboard.secondaryParameters')} ({secondaryParams.length})
            </h2>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
            {secondaryParams.map((param) => (
              <ParameterCard
                key={param.parameter_code}
                param={param}
                onQuickLog={() => {
                  triggerHaptic();
                  onOpenQuickLog(param.parameter_code);
                }}
                onViewTrend={() => {
                  triggerHaptic();
                  onSelectParameterForChart(param.parameter_code);
                  onSelectTab('trends');
                }}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function ParameterCard({ param, onQuickLog, onViewTrend }) {
  const { t } = useTranslation();
  const isDanger = param.status === 'danger_low' || param.status === 'danger_high';
  const isOptimal = param.status === 'optimal';

  const formatRate = (rate, unit) => {
    if (rate === null || rate === undefined || isNaN(Number(rate))) return null;
    const num = Number(rate);
    const sign = num > 0 ? '+' : '';
    return `${sign}${num.toFixed(2)} ${unit}${t('common.perDay')}`;
  };

  return (
    <div className={`glass-panel glass-panel-hover rounded-2xl p-4 sm:p-5 border flex flex-col justify-between transition-all ${
      isDanger ? 'border-coral-500/60 bg-coral-950/20 shadow-neon-coral' : 'border-marine-700/80 bg-marine-900/80'
    }`}>
      <div className="space-y-3">
        {/* Header con Nombre y Estado */}
        <div className="flex items-center justify-between gap-2">
          <span className="font-extrabold text-sm sm:text-base text-slate-100 tracking-tight">
            {param.parameter_name}
          </span>
          <span
            className={`text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full border ${
              isOptimal
                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-neon-emerald'
                : isDanger
                ? 'bg-coral-500/20 text-coral-300 border-coral-500/40 shadow-neon-coral'
                : 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40'
            }`}
          >
            {param.status === 'optimal' ? t('common.optimal') : isDanger ? t('common.danger') : t('common.safeRange')}
          </span>
        </div>

        {/* Gran Display de Valor */}
        <div className="flex items-baseline justify-between">
          <div className="flex items-baseline gap-1.5">
            <span className="text-3xl sm:text-4xl font-black tracking-tight text-white">
              {param.latest_value !== null ? param.latest_value : '--'}
            </span>
            <span className="text-xs sm:text-sm font-bold text-cyan-400">
              {param.unit}
            </span>
          </div>

          {/* Pill de Tasa Diaria */}
          {param.daily_rate !== null && (
            <div
              className={`flex items-center gap-1 text-xs font-black px-2.5 py-1 rounded-xl border ${
                param.daily_rate < 0
                  ? 'bg-amber-500/20 text-amber-300 border-amber-500/40'
                  : 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40 shadow-neon-cyan'
              }`}
            >
              {param.daily_rate < 0 ? (
                <TrendingDown className="w-4 h-4 text-amber-400" />
              ) : (
                <TrendingUp className="w-4 h-4 text-cyan-400" />
              )}
              <span>{formatRate(param.daily_rate, param.unit)}</span>
            </div>
          )}
        </div>

        {/* Mensaje de Diagnóstico / Objetivo */}
        <div className="text-xs text-slate-300 bg-marine-950/80 p-3 rounded-xl border border-marine-800 space-y-1">
          <div className="text-[11px] text-slate-400 flex items-center justify-between">
            <span>{t('dashboard.target')}: <strong className="text-emerald-400 font-bold">{param.target} {param.unit}</strong></span>
            <span>{t('dashboard.safeLimits')}: {param.min_safe} - {param.max_safe}</span>
          </div>
          <p className="text-[11px] leading-snug text-slate-300 font-medium">
            {param.prediction_message}
          </p>
        </div>
      </div>

      {/* Botones Táctiles de Acción Rápida en la Tarjeta */}
      <div className="mt-4 pt-3 border-t border-marine-800 flex items-center justify-between gap-2">
        <button
          onClick={onViewTrend}
          className="min-h-[44px] px-3 rounded-xl text-xs font-bold text-slate-400 hover:text-cyan-300 flex items-center gap-1.5 active:scale-95 transition"
        >
          <Activity className="w-4 h-4 text-cyan-400" />
          <span>{t('trends.viewCurve')}</span>
        </button>

        <button
          onClick={onQuickLog}
          className="min-h-[44px] min-w-[56px] px-3.5 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-marine-950 font-black flex items-center justify-center shadow-neon-cyan active:scale-90 transition"
          title={`Registrar ${param.parameter_name}`}
          aria-label={`Registrar ${param.parameter_name}`}
        >
          <Plus className="w-5 h-5 stroke-[3]" />
        </button>
      </div>
    </div>
  );
}
