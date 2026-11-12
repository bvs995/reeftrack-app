import React, { useState, useEffect } from 'react';
import {
  Droplets,
  Calendar,
  Sparkles,
  Plus,
  Sliders,
  CheckCircle2,
  AlertCircle,
  FileText,
  X
} from 'lucide-react';
import { fetchWaterChanges, recordWaterChange } from '../api';

export default function WaterChangesView({
  tank,
  analytics,
  onWaterChangeLogged
}) {
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showLogModal, setShowLogModal] = useState(false);

  const [simPct, setSimPct] = useState(20);
  const [currentNO3, setCurrentNO3] = useState(20);

  const [volumeLiters, setVolumeLiters] = useState('');
  const [percentage, setPercentage] = useState('');
  const [performedAt, setPerformedAt] = useState('');
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const triggerHaptic = () => {
    if (typeof navigator !== 'undefined' && navigator.vibrate) {
      navigator.vibrate(15);
    }
  };

  useEffect(() => {
    if (tank) {
      loadHistory();
      const no3 = analytics?.parameters?.find(p => p.parameter_code === 'no3');
      if (no3 && no3.latest_value) {
        setCurrentNO3(no3.latest_value);
      }
      const defaultLiters = (tank.volume_liters * 0.2).toFixed(1);
      setVolumeLiters(defaultLiters);
      setPercentage('20');
      setPerformedAt(new Date().toISOString().slice(0, 16));
    }
  }, [tank?.id, analytics]);

  const loadHistory = async () => {
    setLoading(true);
    try {
      const data = await fetchWaterChanges(tank.id);
      setHistory(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const expectedNO3AfterChange = (currentNO3 * (1 - simPct / 100)).toFixed(1);
  const simLiters = ((tank?.volume_liters || 100) * (simPct / 100)).toFixed(1);
  const isReef = tank?.tank_type === 'reef';
  const saltNeededKg = isReef ? ((simLiters * 38.5) / 1000).toFixed(2) : null;

  const handleVolumeChange = (litersVal) => {
    setVolumeLiters(litersVal);
    if (tank?.volume_liters && litersVal) {
      const pct = ((parseFloat(litersVal) / tank.volume_liters) * 100).toFixed(1);
      setPercentage(pct);
    }
  };

  const handlePercentageChange = (pctVal) => {
    setPercentage(pctVal);
    if (tank?.volume_liters && pctVal) {
      const lit = ((tank.volume_liters * parseFloat(pctVal)) / 100).toFixed(1);
      setVolumeLiters(lit);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!volumeLiters || parseFloat(volumeLiters) <= 0) return;

    setSubmitting(true);
    try {
      await recordWaterChange(tank.id, {
        volume_liters: parseFloat(volumeLiters),
        percentage: parseFloat(percentage),
        performed_at: performedAt ? new Date(performedAt).toISOString() : new Date().toISOString(),
        notes: notes || undefined
      });
      triggerHaptic();
      setShowLogModal(false);
      setNotes('');
      loadHistory();
      if (onWaterChangeLogged) onWaterChangeLogged();
    } catch (err) {
      alert('Error al registrar cambio de agua');
    } finally {
      setSubmitting(false);
    }
  };

  const wcPrediction = analytics?.water_change_prediction;

  return (
    <div className="space-y-6 pb-28 max-w-7xl mx-auto px-3 sm:px-6 pt-4">
      {/* Banner Principal con Acentos Neón */}
      <div className="glass-panel rounded-3xl p-5 sm:p-7 border border-cyan-500/30 bg-gradient-to-r from-marine-950 via-marine-900 to-marine-950 shadow-2xl">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="space-y-2">
            <span className="text-xs font-black uppercase tracking-wider text-cyan-400">
              Módulo Predictivo de Regeneración Acuática
            </span>
            <h1 className="text-2xl sm:text-3xl font-black text-white">
              Control de Cambios de Agua & Dilución
            </h1>
            <p className="text-xs sm:text-sm text-slate-300 max-w-2xl font-medium">
              Calcula con precisión nanométrica el volumen para exportar desechos orgánicos acumulados y reponer oligoelementos consumidos.
            </p>
          </div>

          <button
            onClick={() => {
              triggerHaptic();
              setShowLogModal(true);
            }}
            className="btn-touch-primary whitespace-nowrap w-full sm:w-auto"
          >
            <Plus className="w-5 h-5 stroke-[3]" />
            <span>Registrar Nuevo Cambio</span>
          </button>
        </div>

        {/* Notificación Predictiva */}
        {wcPrediction && (
          <div className="mt-6 pt-4 border-t border-marine-800 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs bg-marine-950/90 p-4 rounded-2xl border border-marine-800">
            <div className="flex items-start gap-3">
              <Sparkles className="w-5 h-5 text-cyan-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-extrabold text-white text-sm">Próximo Cambio Sugerido: </span>
                <span className="text-cyan-300 font-extrabold">{wcPrediction.suggested_date} </span>
                <span className="text-slate-300">({wcPrediction.recommended_percentage}% del volumen, aprox {wcPrediction.recommended_liters} Litros).</span>
                <p className="text-xs text-slate-400 mt-1">{wcPrediction.reason}</p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Simulador Interactivo Táctil */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 glass-panel rounded-3xl p-5 sm:p-7 border border-marine-700/80 space-y-6 shadow-2xl">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-xl bg-cyan-500/20 text-cyan-400 border border-cyan-500/40">
                <Sliders className="w-5 h-5" />
              </div>
              <h2 className="text-base sm:text-lg font-black text-white">
                Simulador Dinámico de Dilución
              </h2>
            </div>
            <span className="text-xs font-bold text-slate-400 bg-marine-950 px-3 py-1.5 rounded-xl border border-marine-800">
              {tank.volume_liters} L
            </span>
          </div>

          <p className="text-xs sm:text-sm text-slate-300 font-medium">
            Mueve el deslizador táctil para calcular la dilución instantánea de Nitratos ($NO_3$) y Fosfatos ($PO_4$) con agua pura de ósmosis (RO/DI).
          </p>

          {/* Control deslizador táctil grande */}
          <div className="bg-marine-950/90 p-5 rounded-2xl border border-marine-800 space-y-4">
            <div className="flex items-center justify-between text-xs sm:text-sm font-extrabold">
              <span className="text-slate-300">Porcentaje de Renovación</span>
              <span className="text-2xl font-black text-cyan-400 drop-shadow-[0_0_10px_rgba(6,182,212,0.6)]">
                {simPct}%
              </span>
            </div>

            <input
              type="range"
              min="5"
              max="50"
              step="5"
              value={simPct}
              onChange={(e) => {
                triggerHaptic();
                setSimPct(parseInt(e.target.value));
              }}
              className="w-full accent-cyan-400 cursor-pointer h-3 bg-marine-800 rounded-lg"
            />

            {/* Pills de selección rápida para dedos mojados */}
            <div className="grid grid-cols-4 gap-2 pt-1">
              {[10, 15, 20, 30].map((pct) => (
                <button
                  key={pct}
                  type="button"
                  onClick={() => {
                    triggerHaptic();
                    setSimPct(pct);
                  }}
                  className={`min-h-[44px] rounded-xl text-xs font-black border transition active:scale-95 ${
                    simPct === pct
                      ? 'bg-cyan-500/25 border-cyan-400 text-white shadow-neon-cyan ring-2 ring-cyan-400/50'
                      : 'bg-marine-900 border-marine-700 text-slate-300 hover:text-white'
                  }`}
                >
                  {pct}%
                </button>
              ))}
            </div>
          </div>

          {/* Resultados Numéricos Grandes */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="bg-marine-950/80 p-4 rounded-2xl border border-marine-800 text-center">
              <span className="block text-[11px] text-slate-400 font-black uppercase mb-1">Volumen a Cambiar</span>
              <span className="text-2xl font-black text-white">{simLiters}</span>
              <span className="text-xs text-cyan-400 ml-1 font-bold">Litros</span>
            </div>

            <div className="bg-marine-950/80 p-4 rounded-2xl border border-marine-800 text-center">
              <span className="block text-[11px] text-slate-400 font-black uppercase mb-1">Nitrato Post-Cambio</span>
              <div className="flex items-center justify-center gap-1.5">
                <span className="text-sm line-through text-slate-500 font-bold">{currentNO3}</span>
                <span className="text-2xl font-black text-emerald-400">{expectedNO3AfterChange}</span>
                <span className="text-xs text-slate-400 font-bold">ppm</span>
              </div>
            </div>

            {isReef ? (
              <div className="bg-marine-950/80 p-4 rounded-2xl border border-marine-800 text-center">
                <span className="block text-[11px] text-slate-400 font-black uppercase mb-1">Sal Sintética Estimada</span>
                <span className="text-2xl font-black text-cyan-400">{saltNeededKg}</span>
                <span className="text-xs text-slate-400 ml-1 font-bold">kg (~35 ppt)</span>
              </div>
            ) : (
              <div className="bg-marine-950/80 p-4 rounded-2xl border border-marine-800 text-center">
                <span className="block text-[11px] text-slate-400 font-black uppercase mb-1">Dilución de Compuestos</span>
                <span className="text-2xl font-black text-emerald-400">-{simPct}%</span>
                <span className="text-xs text-slate-400 ml-1 font-bold">residuos</span>
              </div>
            )}
          </div>
        </div>

        {/* Guía Rápida para Dedos Mojados */}
        <div className="glass-panel rounded-3xl p-5 sm:p-6 border border-marine-700/80 flex flex-col justify-between space-y-4 shadow-2xl">
          <div className="space-y-3">
            <h3 className="text-sm font-black text-white flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              Buenas Prácticas del Acuarista
            </h3>
            <ul className="text-xs text-slate-300 space-y-3 font-medium">
              <li className="flex items-start gap-2">
                <span className="text-cyan-400 font-black text-base">•</span>
                <span><strong>Equilibrio Térmico:</strong> Ajusta el calentador del agua nueva a ±0.5°C del acuario antes de introducirla.</span>
              </li>
              {isReef ? (
                <>
                  <li className="flex items-start gap-2">
                    <span className="text-cyan-400 font-black text-base">•</span>
                    <span><strong>Salinidad exacta (1.025):</strong> Usa refractómetro calibrado a 20-25°C para evitar choques osmóticos en acroporas.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-cyan-400 font-black text-base">•</span>
                    <span><strong>Mezcla de la sal:</strong> Oxigena la sal durante 2-3 horas con bomba de flujo para estabilizar el pH.</span>
                  </li>
                </>
              ) : (
                <>
                  <li className="flex items-start gap-2">
                    <span className="text-emerald-400 font-black text-base">•</span>
                    <span><strong>Remineralización RO/DI:</strong> Reponer sales GH (Ca/Mg) y buffer KH para evitar desmineralización de camarones y plantas.</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <span className="text-emerald-400 font-black text-base">•</span>
                    <span><strong>Anticloro:</strong> Neutralizar cloros y cloraminas de inmediato si se utiliza agua de red.</span>
                  </li>
                </>
              )}
            </ul>
          </div>

          <div className="p-3.5 rounded-2xl bg-marine-950/90 border border-marine-800 text-[11px] text-slate-400 font-medium">
            💡 Consejo: Cambios regulares pequeños (10-15% cada semana) aportan una estabilidad infinitamente superior frente a cambios drásticos del 50%.
          </div>
        </div>
      </div>

      {/* Historial de Cambios de Agua */}
      <div className="glass-panel rounded-3xl p-5 sm:p-6 border border-marine-700/80 space-y-4 shadow-2xl">
        <h3 className="text-sm font-black uppercase tracking-wider text-slate-300 flex items-center gap-2">
          <Calendar className="w-4 h-4 text-cyan-400" />
          Historial Registrado ({history.length})
        </h3>

        {history.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-marine-800 text-slate-400 font-bold">
                  <th className="py-3 px-3">Fecha</th>
                  <th className="py-3 px-3">Volumen</th>
                  <th className="py-3 px-3">Porcentaje</th>
                  <th className="py-3 px-3">Sal / Tratamiento y Observaciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-marine-800/80">
                {history.map((wc) => {
                  const d = new Date(wc.performed_at);
                  return (
                    <tr key={wc.id} className="hover:bg-marine-850/60 transition">
                      <td className="py-3 px-3 text-slate-300 font-medium whitespace-nowrap">
                        {d.toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' })}{' '}
                        <span className="text-slate-500">
                          {d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </td>
                      <td className="py-3 px-3 font-black text-white whitespace-nowrap text-sm">
                        {wc.volume_liters} Litros
                      </td>
                      <td className="py-3 px-3">
                        <span className="px-2.5 py-0.5 rounded-full text-[10px] font-black bg-cyan-500/20 text-cyan-300 border border-cyan-400/50">
                          {wc.percentage}%
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-400 font-medium">
                        {wc.notes || '--'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-xs text-slate-400 py-6 text-center font-medium">
            No se han registrado cambios de agua aún.
          </p>
        )}
      </div>

      {/* Modal Táctil Grande para Registrar Cambio de Agua */}
      {showLogModal && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
          <div className="relative w-full max-w-md bg-marine-900 border-t sm:border border-marine-700/80 rounded-t-3xl sm:rounded-3xl shadow-2xl overflow-hidden">
            <div className="flex items-center justify-between p-4 sm:p-5 border-b border-marine-800 bg-marine-950/80">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-cyan-500/20 text-cyan-400 flex items-center justify-center border border-cyan-500/30">
                  <Droplets className="w-5 h-5" />
                </div>
                <h3 className="font-extrabold text-white text-base">Registrar Cambio de Agua</h3>
              </div>
              <button
                onClick={() => setShowLogModal(false)}
                className="w-9 h-9 rounded-xl bg-marine-800 text-slate-400 hover:text-white flex items-center justify-center"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="p-4 sm:p-5 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-[11px] font-bold uppercase text-slate-400 mb-1">
                    Litros Cambiados
                  </label>
                  <input
                    type="number"
                    step="0.5"
                    required
                    value={volumeLiters}
                    onChange={(e) => handleVolumeChange(e.target.value)}
                    className="w-full min-h-[48px] bg-marine-950 border-2 border-marine-700 focus:border-cyan-400 rounded-xl px-3 text-base text-white font-black focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-bold uppercase text-slate-400 mb-1">
                    Porcentaje (%)
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    required
                    value={percentage}
                    onChange={(e) => handlePercentageChange(e.target.value)}
                    className="w-full min-h-[48px] bg-marine-950 border-2 border-marine-700 focus:border-cyan-400 rounded-xl px-3 text-base text-white font-black focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="block text-[11px] font-bold uppercase text-slate-400 mb-1">
                  Fecha y Hora
                </label>
                <input
                  type="datetime-local"
                  value={performedAt}
                  onChange={(e) => setPerformedAt(e.target.value)}
                  className="w-full min-h-[46px] bg-marine-950 border border-marine-700 rounded-xl px-3 text-xs text-slate-200 focus:border-cyan-400 focus:outline-none font-medium"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold uppercase text-slate-400 mb-1">
                  Notas (Sal sintética, acondicionador, sifonado)
                </label>
                <input
                  type="text"
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Ej. Sal Tropic Marin Pro-Reef 1.025, aspirado de detritos"
                  className="w-full min-h-[46px] bg-marine-950 border border-marine-700 rounded-xl px-3 text-xs text-slate-200 placeholder-slate-500 focus:border-cyan-400 focus:outline-none font-medium"
                />
              </div>

              <div className="pt-2 flex items-center justify-end gap-3 safe-bottom">
                <button
                  type="button"
                  onClick={() => setShowLogModal(false)}
                  className="btn-touch-secondary flex-1 sm:flex-none"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="btn-touch-primary flex-1 sm:flex-none"
                >
                  {submitting ? 'Guardando...' : 'Guardar Cambio'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
