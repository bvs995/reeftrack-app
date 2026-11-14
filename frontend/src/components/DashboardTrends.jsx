import React, { useState, useEffect, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import {
  TrendingDown,
  TrendingUp,
  AlertTriangle,
  Droplets,
  Calendar,
  Sparkles,
  ShieldCheck,
  ShieldAlert,
  Activity,
  ArrowRight,
  RefreshCw,
  Info,
  Camera
} from 'lucide-react';
import { fetchPredictions, fetchMeasurements } from '../api';
import ReefAnalysisCard from './ReefAnalysisCard';

// Plugin de anotaciones (Chart.js box annotations) para dibujar franjas de zona segura
const annotationPlugin = {
  id: 'annotation',
  beforeDatasetsDraw(chart, _args, options) {
    const { ctx, chartArea, scales } = chart;
    if (!options?.annotations || !chartArea || !scales?.y) return;

    const { top, bottom, left, right } = chartArea;
    const yScale = scales.y;

    Object.values(options.annotations).forEach((annotation) => {
      if (!annotation || annotation.type !== 'box') return;

      const yMinVal = annotation.yMin !== undefined ? annotation.yMin : 0;
      const yMaxVal = annotation.yMax !== undefined ? annotation.yMax : 0;

      const rawY1 = yScale.getPixelForValue(yMaxVal);
      const rawY2 = yScale.getPixelForValue(yMinVal);

      const yTop = Math.max(top, Math.min(rawY1, rawY2));
      const yBottom = Math.min(bottom, Math.max(rawY1, rawY2));
      const height = Math.max(0, yBottom - yTop);
      const width = right - left;

      if (height <= 0 || width <= 0) return;

      ctx.save();
      ctx.fillStyle = annotation.backgroundColor || 'rgba(16, 185, 129, 0.15)';
      ctx.fillRect(left, yTop, width, height);

      if (annotation.borderWidth && annotation.borderWidth > 0 && annotation.borderColor) {
        ctx.strokeStyle = annotation.borderColor;
        ctx.lineWidth = annotation.borderWidth;
        if (annotation.borderDash) {
          ctx.setLineDash(annotation.borderDash);
        }
        ctx.strokeRect(left, yTop, width, height);
      }
      ctx.restore();
    });
  }
};

// Registrar plugins requeridos de Chart.js
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  annotationPlugin
);

export default function DashboardTrends({
  predictions: propPredictions = null,
  measurements: propMeasurements = null,
  onOpenQuickLog = null,
  onOpenWaterChange = null
}) {
  const { t, i18n } = useTranslation();
  const [predictions, setPredictions] = useState(propPredictions);
  const [measurements, setMeasurements] = useState(propMeasurements || []);
  const [loading, setLoading] = useState(!propPredictions);
  const [activeParam, setActiveParam] = useState('dkh'); // 'dkh', 'calcium', 'nitrate', 'magnesium', 'phosphate', 'salinity'

  const triggerHaptic = (ms = 15) => {
    if (typeof navigator !== 'undefined' && navigator.vibrate) {
      navigator.vibrate(ms);
    }
  };

  useEffect(() => {
    if (!propPredictions || !propMeasurements) {
      loadData();
    } else {
      setPredictions(propPredictions);
      setMeasurements(propMeasurements);
      setLoading(false);
    }
  }, [propPredictions, propMeasurements]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [preds, meas] = await Promise.all([
        fetchPredictions(),
        fetchMeasurements(50, 'asc')
      ]);
      setPredictions(preds);
      setMeasurements(meas);
    } catch (err) {
      console.error('Error al cargar datos de tendencias:', err);
    } finally {
      setLoading(false);
    }
  };

  // Parámetros disponibles y sus configuraciones
  const PARAM_CONFIG = {
    dkh: {
      key: 'alkalinity_dkh',
      name: 'Alcalinidad (dKH)',
      shortName: 'Alcalinidad',
      unit: 'dKH',
      safeMin: 7.5,
      safeMax: 9.0,
      step: 0.1,
      color: '#00f2fe',
      predictionData: predictions?.alkalinity
    },
    calcium: {
      key: 'calcium_ppm',
      name: 'Calcio (Ca)',
      shortName: 'Calcio',
      unit: 'ppm',
      safeMin: 400.0,
      safeMax: 450.0,
      step: 1.0,
      color: '#10b981',
      predictionData: predictions?.calcium
    },
    nitrate: {
      key: 'nitrate_ppm',
      name: 'Nitratos (NO3)',
      shortName: 'Nitratos',
      unit: 'ppm',
      safeMin: 2.0,
      safeMax: 20.0,
      step: 0.1,
      color: '#f59e0b',
      predictionData: null
    },
    magnesium: {
      key: 'magnesium_ppm',
      name: 'Magnesio (Mg)',
      shortName: 'Magnesio',
      unit: 'ppm',
      safeMin: 1280.0,
      safeMax: 1420.0,
      step: 5.0,
      color: '#38bdf8',
      predictionData: null
    },
    phosphate: {
      key: 'phosphate_ppm',
      name: 'Fosfatos (PO4)',
      shortName: 'Fosfatos',
      unit: 'ppm',
      safeMin: 0.02,
      safeMax: 0.08,
      min: 0, // Bloqueo estricto inferior
      suggestedMax: 0.25, // Da un poco de aire por encima del 0.20 actual
      step: 0.01,
      color: '#c084fc',
      predictionData: null
    },
    salinity: {
      key: 'salinity_ppt',
      name: 'Salinidad (SG / ppt)',
      shortName: 'Salinidad',
      unit: 'SG / ppt',
      safeMin: 1.024,
      safeMax: 1.026,
      step: 0.001,
      color: '#0ea5e9',
      predictionData: null
    }
  };

  const currentParam = PARAM_CONFIG[activeParam] || PARAM_CONFIG.dkh;

  // Filtrar lecturas válidas para el parámetro activo
  const validReadings = useMemo(() => {
    return measurements
      .filter(m => m[currentParam.key] !== null && m[currentParam.key] !== undefined)
      .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
  }, [measurements, currentParam.key]);

  // Calcular la pendiente local para proyección de 3 días si no viene precalculada
  const localSlope = useMemo(() => {
    if (validReadings.length < 2) return 0;
    const recent = validReadings.slice(-5);
    const t0 = new Date(recent[0].timestamp).getTime() / 86400000;
    const tLast = new Date(recent[recent.length - 1].timestamp).getTime() / 86400000;
    const spanDays = tLast - t0;

    // Si las lecturas están tomadas a menos de 2 horas de diferencia, asumir estabilidad (tasa 0)
    // para evitar divisiones infinitesimales que disparen pendientes erráticas (ej: -73.11)
    if (spanDays < 0.08) return 0;

    const points = recent.map(r => [
      (new Date(r.timestamp).getTime() / 86400000) - t0,
      Number(r[currentParam.key])
    ]);
    const n = points.length;
    const sumX = points.reduce((acc, p) => acc + p[0], 0);
    const sumY = points.reduce((acc, p) => acc + p[1], 0);
    const sumXY = points.reduce((acc, p) => acc + p[0] * p[1], 0);
    const sumX2 = points.reduce((acc, p) => acc + p[0] ** 2, 0);
    const den = (n * sumX2 - sumX ** 2);
    if (Math.abs(den) < 1e-9) return 0;
    const rawSlope = (n * sumXY - sumX * sumY) / den;

    // Límites biológicos de variación máxima por día para amortiguar ruido
    const maxDailyChange = {
      phosphate_ppm: 0.15,
      alkalinity_dkh: 2.0,
      calcium_ppm: 50.0,
      magnesium_ppm: 100.0,
      nitrate_ppm: 15.0
    };
    const maxLimit = maxDailyChange[currentParam.key] || 5.0;
    return Math.max(-maxLimit, Math.min(maxLimit, rawSlope));
  }, [validReadings, currentParam.key]);

  // Configurar datasets de Chart.js con la zona segura sombreada y línea punteada de 3 días
  const chartData = useMemo(() => {
    if (validReadings.length === 0) return null;

    // 1. Fechas reales
    const realLabels = validReadings.map(r => {
      const d = new Date(r.timestamp);
      return `${d.getDate()}/${d.getMonth() + 1}`;
    });
    const realValues = validReadings.map(r => Number(r[currentParam.key]));

    // 2. Fechas de proyección para los próximos 3 días
    const lastDate = new Date(validReadings[validReadings.length - 1].timestamp);
    const projLabels = [];
    const projValues = new Array(realValues.length - 1).fill(null);
    const ultimoValorReal = realValues[realValues.length - 1];
    const pendienteDiaria = localSlope;

    // El primer valor conecta la línea real con la punteada
    projValues.push(ultimoValorReal);

    // Proyecciones limitadas estrictamente a cero:
    for (let day = 1; day <= 3; day++) {
      const futureDate = new Date(lastDate);
      futureDate.setDate(futureDate.getDate() + day);
      projLabels.push(`+${day}d (${futureDate.getDate()}/${futureDate.getMonth() + 1})`);
      
      const proyeccionDia = Math.max(0, ultimoValorReal + (pendienteDiaria * day));
      projValues.push(Number(proyeccionDia.toFixed(3)));
    }

    const allLabels = [...realLabels, ...projLabels];

    return {
      labels: allLabels,
      datasets: [
        // Medición Real del Acuarista
        {
          label: `Medición Real (${currentParam.unit})`,
          data: [...realValues, null, null, null],
          borderColor: currentParam.color,
          backgroundColor: currentParam.color,
          borderWidth: 3,
          pointBackgroundColor: currentParam.color,
          pointBorderColor: '#ffffff',
          pointBorderWidth: 2,
          pointRadius: 6,
          pointHoverRadius: 8,
          tension: 0.1,
          fill: false,
        },
        // Línea Punteada de Proyección a 3 Días
        {
          label: `Proyección 3 Días (${pendienteDiaria >= 0 ? '+' : ''}${pendienteDiaria.toFixed(2)} ${currentParam.unit}/día)`,
          data: projValues,
          borderColor: '#38bdf8', // Cyan
          borderDash: [6, 6], // Define el estilo punteado
          borderWidth: 2.5,
          pointBackgroundColor: '#38bdf8',
          pointBorderColor: '#ffffff',
          pointBorderWidth: 1.5,
          pointRadius: 4.5,
          pointHoverRadius: 7,
          tension: 0.1,
          fill: false,
        }
      ]
    };
  }, [validReadings, currentParam, localSlope]);

  const isPhosphate = currentParam.key === 'phosphate_ppm' || activeParam === 'phosphate';

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      y: {
        min: 0, // CRÍTICO: Bloquea el eje Y para que nunca sea negativo
        suggestedMax: isPhosphate ? 0.25 : (currentParam.suggestedMax || currentParam.safeMax * 1.1), // Da aire por encima de tu lectura de 0.20
        grid: {
          color: 'rgba(255, 255, 255, 0.05)',
        },
        ticks: { color: '#94a3b8', font: { size: 11, weight: '600' } },
        ...(isPhosphate ? {} : { suggestedMin: currentParam.safeMin ? currentParam.safeMin * 0.9 : 0 })
      },
      x: {
        grid: {
          color: 'rgba(255, 255, 255, 0.05)',
        },
        ticks: { color: '#94a3b8', font: { size: 11, weight: '600' } }
      }
    },
    plugins: {
      legend: {
        display: false, // Oculta la leyenda por defecto si usas la tuya personalizada
      },
      tooltip: {
        backgroundColor: '#0f172a',
        titleColor: '#00f2fe',
        bodyColor: '#f8fafc',
        borderColor: '#334155',
        borderWidth: 1.5,
        padding: 12,
        callbacks: {
          label: (context) => {
            if (context.parsed.y === null) return null;
            return `${context.dataset.label}: ${context.parsed.y} ${currentParam.unit}`;
          }
        }
      },
      annotation: {
        annotations: {
          zonaSegura: {
            type: 'box',
            yMin: isPhosphate ? 0.02 : (currentParam.safeMin !== undefined ? currentParam.safeMin : 0.02), // Límite inferior de fosfatos
            yMax: isPhosphate ? 0.08 : (currentParam.safeMax !== undefined ? currentParam.safeMax : 0.08), // Límite superior de fosfatos
            backgroundColor: 'rgba(16, 185, 129, 0.15)', // Verde translúcido (#10b981 al 15%)
            borderWidth: 0,
            drawTime: 'beforeDatasetsDraw', // Pinta la caja de fondo, detrás de las líneas
          }
        }
      }
    }
  };

  // Datos para las tarjetas predictivas superiores
  const alk = predictions?.alkalinity;
  const wc = predictions?.water_change_prediction;

  // Formatear recomendación de próxima medición para dKH
  const formatNextTestRecommendation = () => {
    if (!alk?.latest_value) {
      return t('trends.noMeasurementsYet');
    }
    if (alk?.days_remaining_safe === null || alk?.days_remaining_safe === undefined) {
      return t('trends.routineIn14Days');
    }
    const days = Number(alk.days_remaining_safe);
    const testDay = new Date();
    testDay.setDate(testDay.getDate() + Math.max(1, Math.floor(days * 0.7)));
    const weekday = testDay.toLocaleDateString(i18n.language || 'es', { weekday: 'long' });
    const dayDate = testDay.toLocaleDateString(i18n.language || 'es', { day: 'numeric', month: 'short' });
    const capitalizedWeekday = weekday.charAt(0).toUpperCase() + weekday.slice(1);
    if (days <= 1) {
      return t('trends.measureToday');
    }
    return t('trends.measureDate', { date: `${capitalizedWeekday}, ${dayDate}` });
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto px-3 sm:px-6 py-4 pb-28">
      {/* Banner de Estado de Confianza Estadística para Nuevas Bases de Datos */}
      {predictions && (predictions.confidence_level === 'low' || (predictions.total_measurements || 0) < 3) && (
        <div className="p-3.5 rounded-2xl bg-amber-500/15 border border-amber-500/40 text-amber-200 text-xs font-semibold flex flex-col sm:flex-row sm:items-center justify-between gap-3 animate-in fade-in">
          <div className="flex items-center gap-2.5 min-w-0">
            <Info className="w-4 h-4 text-amber-400 shrink-0" />
            <span>
              {predictions.confidence_message || t('trends.confidenceNotice')}
            </span>
          </div>
          {onOpenQuickLog && (
            <button
              type="button"
              onClick={onOpenQuickLog}
              className="px-3 py-1 bg-amber-400 hover:bg-amber-300 text-marine-950 font-black rounded-lg text-[11px] self-start sm:self-auto shrink-0 active:scale-95 transition"
            >
              {t('dashboard.quickLogCTA')}
            </button>
          )}
        </div>
      )}

      {/* ---------------- 1. TARJETAS DE ALERTA PREDICTIVA (ARRIBA) ---------------- */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Tarjeta 1: Consumo Diario de Alcalinidad / Buffer */}
        <div className="glass-panel rounded-3xl p-5 border border-cyan-500/40 bg-gradient-to-br from-marine-900/95 via-marine-850 to-marine-900 shadow-neon-cyan relative overflow-hidden flex flex-col justify-between">
          <div className="absolute -right-8 -bottom-8 w-36 h-36 bg-cyan-500/10 rounded-full blur-2xl pointer-events-none" />

          <div className="space-y-3 relative z-10">
            {/* Header con tasa de consumo */}
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-xl bg-cyan-500/20 text-cyan-400 flex items-center justify-center border border-cyan-500/30">
                  <Activity className="w-4 h-4" />
                </div>
                <span className="text-xs font-black uppercase tracking-wider text-cyan-300">
                  {t('trends.alkConsumption')}
                </span>
              </div>

              {/* Tasa calculada en formato destacado */}
              <div className="flex items-center gap-1.5 px-3 py-1 rounded-xl bg-marine-950 border border-marine-700/80">
                {alk?.daily_slope !== null && alk?.daily_slope !== undefined && alk.daily_slope < 0 ? (
                  <TrendingDown className="w-4 h-4 text-amber-400" />
                ) : (
                  <TrendingUp className="w-4 h-4 text-cyan-400" />
                )}
                <span className="text-xs sm:text-sm font-black text-white">
                  {alk?.daily_consumption_rate !== null && alk?.daily_consumption_rate !== undefined
                    ? `${t('trends.consumption')} -${alk.daily_consumption_rate} dKH ${t('common.perDay')}`
                    : `${t('trends.consumption')} ${t('trends.noSufficientData')}`}
                </span>
              </div>
            </div>

            {/* Mensaje Predictivo Dinámico */}
            <div className="bg-marine-950/80 p-3.5 rounded-2xl border border-marine-800 space-y-1.5">
              <p className="text-xs sm:text-sm text-slate-200 font-semibold leading-relaxed">
                {alk?.latest_value === null || alk?.latest_value === undefined ? (
                  t('trends.noMeasurementsYet')
                ) : alk?.days_remaining_safe !== null && alk?.days_remaining_safe !== undefined ? (
                  <>
                    {t('trends.alkSafeMessage', {
                      limit: '7.5 dKH',
                      days: alk.days_remaining_safe,
                      unit: alk.days_remaining_safe === 1 ? t('common.day') : t('common.days')
                    })}
                  </>
                ) : alk?.status === 'insufficient_data' ? (
                  t('trends.alkNeedConsecutive')
                ) : (
                  t('trends.alkNormal')
                )}
              </p>

              <div className="pt-1 flex items-center gap-1.5 text-xs font-extrabold text-cyan-400">
                <Sparkles className="w-3.5 h-3.5 shrink-0" />
                <span>{t('trends.recommendation')} {formatNextTestRecommendation()}</span>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-marine-800 flex items-center justify-between text-xs">
            <span className="text-slate-400 font-medium">
              {t('trends.lastReading')}{' '}
              <strong className="text-white">
                {alk?.latest_value !== null && alk?.latest_value !== undefined ? `${alk.latest_value} dKH` : t('common.noPriorRecord')}
              </strong>
            </span>
            <button
              onClick={() => {
                triggerHaptic();
                setActiveParam('dkh');
              }}
              className="text-cyan-400 hover:text-cyan-300 font-bold flex items-center gap-1"
            >
              {t('trends.viewCurve')} <ArrowRight className="w-3 h-3" />
            </button>
          </div>
        </div>

        {/* Tarjeta 2: Predicción de Nitratos & Cambio de Agua */}
        <div className="glass-panel rounded-3xl p-5 border border-amber-500/40 bg-gradient-to-br from-marine-900/95 via-marine-850 to-marine-900 shadow-lg relative overflow-hidden flex flex-col justify-between">
          <div className="absolute -right-8 -bottom-8 w-36 h-36 bg-amber-500/10 rounded-full blur-2xl pointer-events-none" />

          <div className="space-y-3 relative z-10">
            {/* Header */}
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-xl bg-amber-500/20 text-amber-400 flex items-center justify-center border border-amber-500/30">
                  <Droplets className="w-4 h-4" />
                </div>
                <span className="text-xs font-black uppercase tracking-wider text-amber-300">
                  {t('trends.nitrateAccumulation')}
                </span>
              </div>

              {wc?.daily_accumulation_rate !== null && wc?.daily_accumulation_rate !== undefined ? (
                <div className="flex items-center gap-1.5 px-3 py-1 rounded-xl bg-marine-950 border border-marine-700/80">
                  <TrendingUp className="w-4 h-4 text-amber-400" />
                  <span className="text-xs sm:text-sm font-black text-amber-300">
                    +{Number((wc.daily_accumulation_rate * 7).toFixed(1))} ppm {t('common.perWeek')}
                  </span>
                </div>
              ) : (
                <div className="flex items-center gap-1.5 px-3 py-1 rounded-xl bg-marine-950 border border-marine-700/80 text-xs text-slate-400 font-semibold">
                  <span>{t('trends.noTrend')}</span>
                </div>
              )}
            </div>

            {/* Mensaje de Alerta de Cambio de Agua */}
            <div className="bg-marine-950/80 p-3.5 rounded-2xl border border-marine-800 space-y-1.5">
              <p className="text-xs sm:text-sm text-slate-200 font-semibold leading-relaxed">
                {wc?.current_nitrate_ppm === null || wc?.current_nitrate_ppm === undefined ? (
                  t('trends.noNitrateData')
                ) : wc?.urgency === 'immediate' ? (
                  t('trends.nitrateImmediate', { val: wc.current_nitrate_ppm, pct: wc.suggested_percentage || 20 })
                ) : wc?.days_until_threshold !== null && wc?.days_until_threshold !== undefined ? (
                  <>
                    {t('trends.nitrateRising', {
                      rate: Number(((wc.daily_accumulation_rate || 0) * 7).toFixed(1)),
                      days: wc.days_until_threshold,
                      unit: wc.days_until_threshold === 1 ? t('common.day') : t('common.days')
                    })}{' '}
                    {wc.suggested_water_change_date ? `(${wc.suggested_water_change_date})` : ''}.
                  </>
                ) : (
                  t('trends.nitrateSafe')
                )}
              </p>

              <div className="pt-1 flex items-center gap-1.5 text-xs font-extrabold text-amber-400">
                <Calendar className="w-3.5 h-3.5 shrink-0" />
                <span>
                  {t('trends.estimatedDate')}{' '}
                  {wc?.suggested_water_change_date
                    ? wc.suggested_water_change_date
                    : wc?.current_nitrate_ppm !== null && wc?.current_nitrate_ppm !== undefined
                    ? t('trends.routineIn14Days')
                    : t('trends.pendingMeasurements')}
                </span>
              </div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-marine-800 flex items-center justify-between text-xs">
            <span className="text-slate-400 font-medium">
              {t('trends.currentReading')}{' '}
              <strong className="text-white">
                {wc?.current_nitrate_ppm !== null && wc?.current_nitrate_ppm !== undefined
                  ? `${wc.current_nitrate_ppm} ppm`
                  : t('trends.noSufficientData')}
              </strong>
            </span>
            <button
              onClick={() => {
                triggerHaptic();
                setActiveParam('nitrate');
              }}
              className="text-amber-400 hover:text-amber-300 font-bold flex items-center gap-1"
            >
              {t('trends.viewAccumulation')} <ArrowRight className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>

      {/* ---------------- 2. SELECTOR DE PARÁMETRO INTERACTIVO ---------------- */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
        {Object.entries(PARAM_CONFIG).map(([key, config]) => {
          const isSelected = activeParam === key;
          return (
            <button
              key={key}
              onClick={() => {
                triggerHaptic();
                setActiveParam(key);
              }}
              className={`min-h-[46px] flex-shrink-0 flex items-center gap-2 px-4 py-2.5 rounded-2xl text-xs sm:text-sm font-black transition-all border select-none active:scale-95 ${
                isSelected
                  ? 'bg-cyan-500/25 border-cyan-400 text-white shadow-neon-cyan ring-2 ring-cyan-400/40'
                  : 'bg-marine-900 border-marine-700/80 text-slate-400 hover:text-slate-200 hover:bg-marine-850'
              }`}
            >
              <span>{config.shortName}</span>
              <span className="text-[11px] font-bold text-cyan-400">({config.unit})</span>
            </button>
          );
        })}
      </div>

      {/* ---------------- 3. GRÁFICA INTERACTIVA CON ZONA SEGURA & PROYECCIÓN ---------------- */}
      <div className="glass-panel rounded-3xl p-5 sm:p-7 border border-marine-700/80 space-y-4 shadow-2xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-3 border-b border-marine-800">
          <div>
            <div className="flex items-center gap-2.5">
              <h2 className="text-xl sm:text-2xl font-black text-white">
                {currentParam.name}
              </h2>
              <span className="text-xs font-black px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 flex items-center gap-1">
                <ShieldCheck className="w-3 h-3 text-emerald-400" />
                Zona Segura: {currentParam.safeMin} - {currentParam.safeMax} {currentParam.unit}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1 font-medium">
              Serie histórica con <strong className="text-emerald-400">franja verde de rango seguro</strong> y <strong className="text-amber-400">proyección punteada a 3 días</strong>.
            </p>
          </div>

          {/* Quick Metrics & Actions */}
          <div className="flex items-center gap-2.5 flex-wrap">
            {onOpenQuickLog && (
              <button
                type="button"
                onClick={() => {
                  triggerHaptic(25);
                  onOpenQuickLog();
                }}
                className="btn-touch py-2 px-3 rounded-xl bg-gradient-to-r from-cyan-500 to-emerald-400 hover:from-cyan-400 hover:to-emerald-300 text-marine-950 font-black text-xs shadow-neon-cyan flex items-center gap-1.5 active:scale-95"
              >
                <Camera className="w-3.5 h-3.5 stroke-[2.5]" />
                <span>Escanear / Registrar</span>
              </button>
            )}

            <div className="bg-marine-950 px-3.5 py-2 rounded-xl border border-marine-800 text-right">
              <span className="block text-[10px] font-black uppercase text-slate-400">Pendiente Diaria</span>
              <span className={`text-sm font-black flex items-center justify-end gap-1 ${
                localSlope < 0 ? 'text-amber-400' : 'text-cyan-400'
              }`}>
                {localSlope < 0 ? <TrendingDown className="w-3.5 h-3.5" /> : <TrendingUp className="w-3.5 h-3.5" />}
                {localSlope > 0 ? '+' : ''}{localSlope.toFixed(3)} {currentParam.unit}/d
              </span>
            </div>

            <div className="bg-marine-950 px-3.5 py-2 rounded-xl border border-marine-800 text-right">
              <span className="block text-[10px] font-black uppercase text-slate-400">Proyección +3 Días</span>
              <span className="text-sm font-black text-white">
                {validReadings.length > 0
                  ? `${(Number(validReadings[validReadings.length - 1][currentParam.key]) + localSlope * 3).toFixed(2)} ${currentParam.unit}`
                  : '--'}
              </span>
            </div>
          </div>
        </div>

        {/* Canvas de Chart.js */}
        <div className="h-80 sm:h-96 w-full pt-1">
          {loading ? (
            <div className="h-full flex items-center justify-center text-slate-400 gap-2">
              <Activity className="w-6 h-6 animate-spin text-cyan-400" />
              <span className="text-xs font-semibold">Generando proyección matemática...</span>
            </div>
          ) : !chartData ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-400 gap-2">
              <Info className="w-8 h-8 text-slate-500" />
              <p className="text-xs font-semibold">No hay mediciones registradas para {currentParam.name}.</p>
            </div>
          ) : (
            <Line data={chartData} options={chartOptions} />
          )}
        </div>

        {/* Leyenda Explicativa de la Gráfica */}
        <div className="pt-3 border-t border-marine-800 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400">
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded-full bg-cyan-400" />
              <span className="text-slate-300 font-semibold">Medición Real</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 border-t-2 border-dashed border-amber-400" />
              <span className="text-slate-300 font-semibold">Proyección Punteada (+3 días)</span>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="w-3 h-3 rounded bg-emerald-500/20 border border-emerald-500/40" />
              <span className="text-slate-300 font-semibold">Zona de Rango Seguro</span>
            </div>
          </div>

          <button
            onClick={loadData}
            className="flex items-center gap-1 text-[11px] font-bold text-slate-400 hover:text-cyan-300 transition"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Actualizar Gráfica</span>
          </button>
        </div>
      </div>

      {/* Tarjeta de Diagnóstico Predictivo AquaPulse con IA */}
      <div className="pt-2">
        <ReefAnalysisCard
          aquariumData={{
            nombre_acuario: 'Mi Acuario Principal',
            volumen_litros: 280,
            ph: 8.2,
            kh: alk?.latest_value ?? 8.3,
            calcio: propPredictions?.calcium?.latest_value ?? 420,
            magnesio: 1350,
            nitrato: wc?.current_nitrate_ppm ?? 5.0,
            fosfato: 0.04,
            tendencia_reciente: `Consumo KH: ${alk?.daily_consumption_rate ? alk.daily_consumption_rate.toFixed(2) + ' dKH/d' : 'Estable'}. Acumulación NO3: ${wc?.daily_accumulation_rate ? wc.daily_accumulation_rate.toFixed(2) + ' ppm/d' : 'Estable'}.`
          }}
        />
      </div>
    </div>
  );
}
