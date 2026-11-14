import React, { useState, useEffect } from 'react';
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
  Activity,
  TrendingDown,
  TrendingUp,
  Trash2,
  Calendar,
  AlertCircle,
  Clock,
  Sparkles,
  Info
} from 'lucide-react';
import { fetchChartData, deleteMeasurement } from '../api';

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

export default function TrendsView({
  tank,
  parameters = [],
  selectedCode,
  onSelectCode,
  analytics,
  onMeasurementDeleted
}) {
  const [chartData, setChartData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeCode, setActiveCode] = useState(selectedCode || (parameters[0]?.code || 'dkh'));

  const triggerHaptic = () => {
    if (typeof navigator !== 'undefined' && navigator.vibrate) {
      navigator.vibrate(15);
    }
  };

  useEffect(() => {
    if (selectedCode) {
      setActiveCode(selectedCode);
    }
  }, [selectedCode]);

  useEffect(() => {
    if (tank && activeCode) {
      loadChart();
    }
  }, [tank?.id, activeCode]);

  const loadChart = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchChartData(tank.id, activeCode);
      setChartData(data[activeCode] || null);
    } catch (err) {
      setError('Error al cargar la serie temporal.');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (measId) => {
    if (!window.confirm('¿Seguro que deseas eliminar esta medición?')) return;
    try {
      await deleteMeasurement(measId);
      loadChart();
      if (onMeasurementDeleted) onMeasurementDeleted();
    } catch (err) {
      alert('Error al eliminar medición');
    }
  };

  const paramAnalytic = analytics?.parameters?.find(p => p.parameter_code === activeCode);
  const meta = chartData?.meta || parameters.find(p => p.code === activeCode) || {};
  const points = chartData?.points || [];

  const prepareChartConfig = () => {
    if (!points || points.length === 0) return null;

    const labels = points.map(p => {
      const d = new Date(p.date);
      return `${d.getDate()}/${d.getMonth() + 1}`;
    });
    const values = points.map(p => p.value);

    const datasets = [
      {
        label: `Medición Real (${meta.unit})`,
        data: values,
        borderColor: '#00f2fe',
        backgroundColor: 'rgba(0, 242, 254, 0.12)',
        fill: true,
        tension: 0.35,
        pointBackgroundColor: '#00f2fe',
        pointBorderColor: '#ffffff',
        pointBorderWidth: 2,
        pointRadius: 6,
        pointHoverRadius: 8,
      }
    ];

    if (paramAnalytic?.daily_rate && points.length >= 2) {
      const lastVal = values[values.length - 1];
      const rate = paramAnalytic.daily_rate;
      
      const lastDate = new Date(points[points.length - 1].date);
      const projLabels = [...labels];
      const projValues = new Array(values.length - 1).fill(null);
      projValues.push(lastVal);

      for (let i = 1; i <= 4; i++) {
        const nextD = new Date(lastDate);
        nextD.setDate(nextD.getDate() + i * 2);
        projLabels.push(`${nextD.getDate()}/${nextD.getMonth() + 1} (Proj)`);
        // Al calcular los puntos de la línea punteada:
        const valorProyectado = lastVal + (rate * (i * 2));
        // Forzar a que nunca baje de cero
        const valorPintado = Math.max(0, valorProyectado);
        projValues.push(Number(valorPintado.toFixed(2)));
      }

      datasets.push({
        label: `Proyección (${rate > 0 ? '+' : ''}${rate} ${meta.unit}/día)`,
        data: projValues,
        borderColor: rate < 0 ? '#f59e0b' : '#38bdf8',
        borderDash: [6, 6],
        borderWidth: 2.5,
        pointRadius: 5,
        pointBackgroundColor: rate < 0 ? '#f59e0b' : '#38bdf8',
        fill: false,
        tension: 0.2
      });

      return { labels: projLabels, datasets };
    }

    return { labels, datasets };
  };

  const chartConfig = prepareChartConfig();

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
        labels: {
          color: '#cbd5e1',
          font: { size: 12, weight: '700' }
        }
      },
      tooltip: {
        backgroundColor: '#0f172a',
        titleColor: '#00f2fe',
        bodyColor: '#f8fafc',
        borderColor: '#06b6d4',
        borderWidth: 1.5,
        padding: 12,
        callbacks: {
          label: (context) => `${context.dataset.label}: ${context.parsed.y} ${meta.unit || ''}`
        }
      },
      annotation: {
        annotations: {
          zonaSegura: {
            type: 'box',
            yMin: (activeCode === 'po4' || activeCode === 'phosphate') ? 0.02 : (meta.min_safe !== undefined ? meta.min_safe : 0.02), // Límite inferior del fosfato
            yMax: (activeCode === 'po4' || activeCode === 'phosphate') ? 0.08 : (meta.max_safe !== undefined ? meta.max_safe : 0.08), // Límite superior del fosfato
            backgroundColor: 'rgba(16, 185, 129, 0.15)', // Verde esmeralda traslúcido
            borderWidth: 0, // Sin bordes duros
            drawTime: 'beforeDatasetsDraw' // Dibuja la franja POR DEBAJO de las líneas
          }
        }
      }
    },
    scales: {
      x: {
        grid: { color: 'rgba(255, 255, 255, 0.05)' },
        ticks: { color: '#94a3b8', font: { size: 11, weight: '600' } }
      },
      y: {
        min: (activeCode === 'po4' || activeCode === 'phosphate') ? 0 : undefined, // Bloqueo estricto inferior
        suggestedMax: (activeCode === 'po4' || activeCode === 'phosphate') ? 0.25 : (meta.max_safe ? meta.max_safe * 1.1 : undefined), // Da un poco de aire por encima del 0.20 actual
        grid: {
          color: 'rgba(255, 255, 255, 0.05)' // Líneas sutiles para el tema oscuro
        },
        ticks: { color: '#94a3b8', font: { size: 11, weight: '600' } },
        suggestedMin: meta.min_safe ? meta.min_safe * 0.9 : undefined
      }
    }
  };

  return (
    <div className="space-y-6 pb-28 max-w-7xl mx-auto px-3 sm:px-6 pt-4">
      {/* Botones Grandes de Selección de Parámetro para Móvil */}
      <div className="flex items-center gap-2.5 overflow-x-auto pb-2 scrollbar-none">
        {parameters.map((p) => {
          const isSelected = p.code === activeCode;
          return (
            <button
              key={p.code}
              onClick={() => {
                triggerHaptic();
                setActiveCode(p.code);
                if (onSelectCode) onSelectCode(p.code);
              }}
              className={`min-h-[48px] flex-shrink-0 flex items-center gap-2 px-4 py-2.5 rounded-2xl text-xs sm:text-sm font-extrabold transition-all border active:scale-95 ${
                isSelected
                  ? 'bg-cyan-500/20 text-cyan-300 border-cyan-400 shadow-neon-cyan ring-2 ring-cyan-400/40'
                  : 'bg-marine-900 text-slate-300 border-marine-700 hover:text-white hover:bg-marine-850'
              }`}
            >
              <span>{p.name.split('(')[0]}</span>
              <span className="text-[11px] font-bold text-cyan-400">({p.unit})</span>
            </button>
          );
        })}
      </div>

      {/* Main Chart Card con Estilo Náutico Neón */}
      <div className="glass-panel rounded-3xl p-5 sm:p-7 border border-marine-700/80 space-y-5 shadow-2xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-marine-800">
          <div>
            <div className="flex items-center gap-2.5">
              <h2 className="text-xl sm:text-2xl font-black text-white">
                {meta.name || activeCode.toUpperCase()}
              </h2>
              <span className="text-xs font-black px-2.5 py-0.5 rounded-full bg-cyan-500/20 text-cyan-300 border border-cyan-400/50">
                {meta.unit}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-1 max-w-xl font-medium">
              {meta.description || 'Monitoreo de tendencia y tasa de agotamiento o acumulación en el tanque.'}
            </p>
          </div>

          {/* Quick Metrics */}
          <div className="flex items-center gap-2.5 flex-wrap">
            <div className="bg-marine-950/80 px-4 py-2.5 rounded-2xl border border-marine-800 text-right">
              <span className="block text-[10px] uppercase font-black text-slate-400">Objetivo</span>
              <span className="text-sm sm:text-base font-black text-emerald-400">
                {meta.optimal_target} {meta.unit}
              </span>
            </div>

            <div className="bg-marine-950/80 px-4 py-2.5 rounded-2xl border border-marine-800 text-right">
              <span className="block text-[10px] uppercase font-black text-slate-400">Rango Seguro</span>
              <span className="text-sm sm:text-base font-black text-white">
                {meta.min_safe} - {meta.max_safe}
              </span>
            </div>

            {paramAnalytic?.daily_rate !== null && paramAnalytic?.daily_rate !== undefined && (
              <div className="bg-marine-950/80 px-4 py-2.5 rounded-2xl border border-marine-800 text-right">
                <span className="block text-[10px] uppercase font-black text-slate-400">Tasa Diaria</span>
                <span className={`text-sm sm:text-base font-black flex items-center justify-end gap-1 ${
                  paramAnalytic.daily_rate < 0 ? 'text-amber-400' : 'text-cyan-400'
                }`}>
                  {paramAnalytic.daily_rate < 0 ? <TrendingDown className="w-4 h-4" /> : <TrendingUp className="w-4 h-4" />}
                  {paramAnalytic.daily_rate > 0 ? '+' : ''}{paramAnalytic.daily_rate}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Mensaje de Diagnóstico */}
        {paramAnalytic?.prediction_message && (
          <div className="p-3.5 rounded-2xl bg-marine-950 border border-cyan-500/30 flex items-start gap-3 text-xs text-slate-200 shadow-neon-cyan">
            <Sparkles className="w-5 h-5 text-cyan-400 shrink-0 mt-0.5" />
            <div>
              <strong className="text-cyan-300 font-extrabold">Diagnóstico Predictivo: </strong>
              <span className="font-medium">{paramAnalytic.prediction_message}</span>
            </div>
          </div>
        )}

        {/* Canvas de Gráfica */}
        <div className="h-72 sm:h-96 w-full pt-2">
          {loading ? (
            <div className="h-full flex items-center justify-center text-slate-400 gap-2">
              <Activity className="w-6 h-6 animate-spin text-cyan-400" />
              <span className="text-xs font-semibold">Cargando serie temporal...</span>
            </div>
          ) : points.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-slate-400 gap-2">
              <AlertCircle className="w-8 h-8 text-slate-500" />
              <p className="text-xs font-semibold">No hay mediciones registradas para {meta.name || activeCode}.</p>
            </div>
          ) : chartConfig ? (
            <Line data={chartConfig} options={chartOptions} />
          ) : null}
        </div>
      </div>

      {/* Historial Tabular con Botones Táctiles */}
      <div className="glass-panel rounded-3xl p-5 sm:p-6 border border-marine-700/80 space-y-4">
        <h3 className="text-sm font-black uppercase tracking-wider text-slate-300 flex items-center gap-2">
          <Calendar className="w-4 h-4 text-cyan-400" />
          Historial de Mediciones ({points.length})
        </h3>

        {points.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-marine-800 text-slate-400 font-bold">
                  <th className="py-3 px-3">Fecha y Hora</th>
                  <th className="py-3 px-3">Valor</th>
                  <th className="py-3 px-3">Estado</th>
                  <th className="py-3 px-3">Reactivo / Notas</th>
                  <th className="py-3 px-3 text-right">Acción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-marine-800/80">
                {[...points].reverse().map((p) => {
                  const d = new Date(p.date);
                  const isOutOfRange = p.value < meta.min_safe || p.value > meta.max_safe;
                  return (
                    <tr key={p.id} className="hover:bg-marine-850/60 transition">
                      <td className="py-3 px-3 text-slate-300 font-medium whitespace-nowrap">
                        {d.toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' })}{' '}
                        <span className="text-slate-500">
                          {d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </td>
                      <td className="py-3 px-3 font-black text-white whitespace-nowrap text-sm">
                        {p.value} <span className="text-cyan-400 font-bold text-xs">{meta.unit}</span>
                      </td>
                      <td className="py-3 px-3">
                        <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-black ${
                          isOutOfRange
                            ? 'bg-coral-500/20 text-coral-300 border border-coral-500/40'
                            : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                        }`}>
                          {isOutOfRange ? 'Desviado' : 'Correcto'}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-400 max-w-xs truncate font-medium">
                        {p.notes || '--'}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <button
                          onClick={() => {
                            triggerHaptic();
                            handleDelete(p.id);
                          }}
                          title="Eliminar registro"
                          className="w-9 h-9 rounded-xl inline-flex items-center justify-center text-slate-400 hover:text-coral-400 hover:bg-coral-500/10 transition active:scale-90"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-slate-400 py-6 text-center font-medium">
            No se han registrado mediciones todavía.
          </p>
        )}
      </div>
    </div>
  );
}
