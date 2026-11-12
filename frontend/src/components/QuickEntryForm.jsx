import React, { useState, useEffect } from 'react';
import {
  Waves,
  Check,
  Droplets,
  Activity,
  Layers,
  Sparkles,
  AlertCircle,
  Clock,
  FileText,
  CheckCircle2,
  Calendar,
  Camera
} from 'lucide-react';
import { saveMeasurement, fetchMeasurements } from '../api';
import CameraScannerModal from './CameraScannerModal';

export default function QuickEntryForm({
  onSuccess,
  onCancel,
  initialLastMeasurement = null
}) {
  const [formData, setFormData] = useState({
    alkalinity_dkh: '',
    calcium_ppm: '',
    magnesium_ppm: '',
    nitrate_ppm: '',
    phosphate_ppm: '',
    salinity_ppt: '',
    notes: '',
    timestamp: new Date().toISOString().slice(0, 16)
  });

  const [lastMeasurement, setLastMeasurement] = useState(initialLastMeasurement);
  const [loading, setLoading] = useState(false);
  const [successStatus, setSuccessStatus] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);

  // Estados para captura y escaneo visual por cámara
  const [isScannerOpen, setIsScannerOpen] = useState(false);
  const [activeScanParam, setActiveScanParam] = useState(null);
  const [scannedHighlight, setScannedHighlight] = useState(null);

  // Feedback háptico táctil en dispositivos móviles
  const triggerHaptic = (pattern = 25) => {
    if (typeof navigator !== 'undefined' && navigator.vibrate) {
      navigator.vibrate(pattern);
    }
  };

  // Cargar la última medición como referencia si no se pasó por props
  useEffect(() => {
    if (!initialLastMeasurement) {
      loadLatestMeasurement();
    }
  }, [initialLastMeasurement]);

  const loadLatestMeasurement = async () => {
    try {
      const data = await fetchMeasurements(1, 'desc');
      if (data && data.length > 0) {
        setLastMeasurement(data[0]);
      }
    } catch (err) {
      console.warn('No se pudo cargar la última medición de referencia:', err);
    }
  };

  const handleChange = (field, val) => {
    setFormData(prev => ({ ...prev, [field]: val }));
  };

  const handleScanComplete = (result) => {
    if (result && result.parameter && result.value !== null && result.value !== undefined) {
      setFormData(prev => ({
        ...prev,
        [result.parameter]: String(result.value),
        notes: result.kit_detected
          ? (prev.notes ? `${prev.notes} | ${result.kit_detected}` : result.kit_detected)
          : prev.notes
      }));

      setScannedHighlight({
        parameter: result.parameter,
        value: result.value,
        kit_detected: result.kit_detected,
        notes: result.notes
      });

      triggerHaptic([40, 60, 100]);
    }
  };

  const openScanner = (paramKey = null) => {
    setActiveScanParam(paramKey);
    setIsScannerOpen(true);
    triggerHaptic(30);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage(null);

    // Validar que al menos un campo numérico contenga información
    const fieldsToSubmit = {};
    let hasValue = false;

    const numericKeys = [
      'alkalinity_dkh',
      'calcium_ppm',
      'magnesium_ppm',
      'nitrate_ppm',
      'phosphate_ppm',
      'salinity_ppt'
    ];

    numericKeys.forEach(key => {
      const val = formData[key];
      if (val !== '' && val !== null && !isNaN(parseFloat(val))) {
        fieldsToSubmit[key] = parseFloat(val);
        hasValue = true;
      }
    });

    if (!hasValue) {
      setErrorMessage('Ingresa al menos un parámetro para registrar la medición.');
      triggerHaptic([50, 50, 50]);
      return;
    }

    if (formData.notes?.trim()) {
      fieldsToSubmit.notes = formData.notes.trim();
    }

    if (formData.timestamp) {
      fieldsToSubmit.timestamp = new Date(formData.timestamp).toISOString();
    }

    setLoading(true);
    try {
      const saved = await saveMeasurement(fieldsToSubmit);
      
      // Confirmación táctil y visual exitosa
      triggerHaptic([40, 60, 100]);
      setSuccessStatus(true);
      setLastMeasurement(saved);

      setTimeout(() => {
        setSuccessStatus(false);
        // Limpiar campos numéricos manteniendo fecha y notas
        setFormData(prev => ({
          ...prev,
          alkalinity_dkh: '',
          calcium_ppm: '',
          magnesium_ppm: '',
          nitrate_ppm: '',
          phosphate_ppm: '',
          salinity_ppt: '',
          notes: ''
        }));
        if (onSuccess) onSuccess(saved);
      }, 1200);

    } catch (err) {
      setErrorMessage(err.message || 'Error al guardar la medición');
      triggerHaptic([80, 50, 80]);
    } finally {
      setLoading(false);
    }
  };

  // Definición de las 6 tarjetas compactas de parámetros
  const PARAM_CARDS = [
    {
      key: 'alkalinity_dkh',
      label: 'Alcalinidad',
      unit: 'dKH',
      step: '0.1',
      placeholder: '8.3',
      safeRange: '7.5 - 9.0 dKH',
      accentColor: 'border-cyan-500/40 focus-within:border-cyan-400 focus-within:ring-cyan-400/20',
      badgeColor: 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30',
      lastValue: lastMeasurement?.alkalinity_dkh
    },
    {
      key: 'calcium_ppm',
      label: 'Calcio',
      unit: 'ppm',
      step: '1',
      placeholder: '420',
      safeRange: '400 - 450 ppm',
      accentColor: 'border-emerald-500/40 focus-within:border-emerald-400 focus-within:ring-emerald-400/20',
      badgeColor: 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30',
      lastValue: lastMeasurement?.calcium_ppm
    },
    {
      key: 'magnesium_ppm',
      label: 'Magnesio',
      unit: 'ppm',
      step: '5',
      placeholder: '1350',
      safeRange: '1280 - 1420 ppm',
      accentColor: 'border-blue-500/40 focus-within:border-blue-400 focus-within:ring-blue-400/20',
      badgeColor: 'bg-blue-500/10 text-blue-300 border-blue-500/30',
      lastValue: lastMeasurement?.magnesium_ppm
    },
    {
      key: 'nitrate_ppm',
      label: 'Nitratos (NO3)',
      unit: 'ppm',
      step: '0.1',
      placeholder: '5.0',
      safeRange: '< 20.0 ppm',
      accentColor: 'border-amber-500/40 focus-within:border-amber-400 focus-within:ring-amber-400/20',
      badgeColor: 'bg-amber-500/10 text-amber-300 border-amber-500/30',
      lastValue: lastMeasurement?.nitrate_ppm
    },
    {
      key: 'phosphate_ppm',
      label: 'Fosfatos (PO4)',
      unit: 'ppm',
      step: '0.01',
      placeholder: '0.04',
      safeRange: '0.02 - 0.08 ppm',
      accentColor: 'border-purple-500/40 focus-within:border-purple-400 focus-within:ring-purple-400/20',
      badgeColor: 'bg-purple-500/10 text-purple-300 border-purple-500/30',
      lastValue: lastMeasurement?.phosphate_ppm
    },
    {
      key: 'salinity_ppt',
      label: 'Salinidad / Gravedad',
      unit: 'SG / ppt',
      step: '0.001',
      placeholder: '1.025 o 35.0',
      safeRange: '1.024 - 1.026 / 35 ppt',
      accentColor: 'border-sky-500/40 focus-within:border-sky-400 focus-within:ring-sky-400/20',
      badgeColor: 'bg-sky-500/10 text-sky-300 border-sky-500/30',
      lastValue: lastMeasurement?.salinity_ppt
    }
  ];

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Banner Principal de Captura Visual con Cámara */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-3.5 rounded-2xl bg-gradient-to-r from-marine-900 via-marine-850 to-marine-900 border border-cyan-500/30 shadow-lg">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center text-cyan-400 shrink-0">
            <Camera className="w-5 h-5 stroke-[2.2]" />
          </div>
          <div>
            <div className="text-xs font-black text-white flex items-center gap-2">
              <span>Captura Rápida por Fotografía</span>
              <span className="text-[10px] font-bold px-1.5 py-0.2 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 flex items-center gap-1">
                <Sparkles className="w-2.5 h-2.5" /> IA Vision
              </span>
            </div>
            <div className="text-[11px] text-slate-400">
              Usa la cámara trasera para leer pantallas Hanna Checker o viales Salifert
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={() => openScanner(null)}
          className="btn-touch py-2.5 px-4 bg-gradient-to-r from-cyan-500 via-cyan-400 to-emerald-400 hover:from-cyan-400 hover:to-emerald-300 text-marine-950 font-black text-xs rounded-xl shadow-neon-cyan active:scale-95 flex items-center justify-center gap-2"
        >
          <Camera className="w-4 h-4 stroke-[2.5]" />
          <span>Escanear Lectura</span>
        </button>
      </div>

      {/* Banner de confirmación de lectura autocompletada por IA */}
      {scannedHighlight && (
        <div className="p-3.5 rounded-2xl bg-cyan-500/15 border border-cyan-500/50 text-cyan-200 text-xs font-semibold flex items-center justify-between gap-2 animate-in fade-in slide-in-from-top-2 shadow-lg">
          <div className="flex items-center gap-2.5 min-w-0">
            <Sparkles className="w-5 h-5 text-cyan-400 shrink-0 animate-pulse" />
            <div className="min-w-0">
              <div className="font-extrabold text-white text-xs truncate">
                ¡Parámetro detectado por foto: <span className="text-cyan-300 font-mono">{scannedHighlight.value}</span>!
              </div>
              <div className="text-[11px] text-slate-300">
                Se completó automáticamente en el formulario. Revisa el valor antes de guardar.
                {scannedHighlight.kit_detected && (
                  <span className="text-cyan-300 ml-1.5 font-bold">({scannedHighlight.kit_detected})</span>
                )}
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setScannedHighlight(null)}
            className="text-slate-400 hover:text-white p-1.5 rounded-lg hover:bg-marine-800 transition-colors shrink-0"
            title="Descartar aviso"
          >
            ✕
          </button>
        </div>
      )}

      {/* Mensaje de error si aplica */}
      {errorMessage && (
        <div className="p-3.5 rounded-2xl bg-coral-500/15 border border-coral-500/40 text-coral-300 text-xs font-semibold flex items-center gap-2 animate-in fade-in">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Grid de 6 Tarjetas Compactas con Teclado Numérico en Móviles */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
        {PARAM_CARDS.map((card) => {
          const isHighlighted = scannedHighlight?.parameter === card.key;
          return (
            <div
              key={card.key}
              className={`glass-panel rounded-2xl p-4 border bg-marine-900/90 transition-all flex flex-col justify-between ${
                isHighlighted
                  ? 'ring-2 ring-cyan-400 border-cyan-400 shadow-[0_0_20px_rgba(0,242,254,0.35)] scale-[1.01]'
                  : card.accentColor
              } focus-within:ring-2`}
            >
              {/* Header de la tarjeta con nombre, escáner rápido y badge de rango seguro */}
              <div className="flex items-center justify-between gap-2 mb-2.5">
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className="font-extrabold text-sm text-slate-100 tracking-tight truncate">
                    {card.label}
                  </span>
                  <button
                    type="button"
                    onClick={() => openScanner(card.key)}
                    className="p-1 rounded-lg text-slate-400 hover:text-cyan-300 hover:bg-marine-800 transition-colors"
                    title={`Escanear foto para ${card.label}`}
                  >
                    <Camera className="w-3.5 h-3.5" />
                  </button>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  {isHighlighted && (
                    <span className="text-[9px] font-black px-1.5 py-0.5 rounded-md bg-cyan-400 text-marine-950 animate-pulse">
                      IA
                    </span>
                  )}
                  <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${card.badgeColor}`}>
                    {card.safeRange}
                  </span>
                </div>
              </div>

              {/* Input Numérico con apertura de teclado numérico en móvil */}
              <div className="relative flex items-center">
                <input
                  type="number"
                  step={card.step}
                  inputMode="decimal"
                  value={formData[card.key]}
                  onChange={(e) => handleChange(card.key, e.target.value)}
                  placeholder={card.placeholder}
                  className={`w-full min-h-[50px] bg-marine-950 border ${
                    isHighlighted ? 'border-cyan-400/80 text-cyan-100' : 'border-marine-700/80 text-white'
                  } rounded-xl px-3.5 text-xl font-black focus:outline-none focus:border-cyan-400 placeholder:text-slate-600 tracking-wide shadow-inner`}
                />
                <span className="absolute right-3.5 text-xs font-extrabold text-cyan-400 pointer-events-none select-none">
                  {card.unit}
                </span>
              </div>

              {/* Valor de la última medición justo debajo como referencia gris clara */}
              <div className="mt-2.5 flex items-center justify-between text-xs text-slate-400 select-none">
                <span className="font-medium">Última lectura:</span>
                <span className="font-bold text-slate-300 bg-marine-950 px-2 py-0.5 rounded-lg border border-marine-800">
                  {card.lastValue !== null && card.lastValue !== undefined
                    ? `${card.lastValue} ${card.unit}`
                    : 'Sin registro previo'}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Fila compacta opcional: Fecha y Notas del Kit */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
        <div className="glass-panel p-3.5 rounded-2xl border border-marine-800 bg-marine-900/60 flex items-center gap-2.5">
          <Calendar className="w-4 h-4 text-cyan-400 shrink-0" />
          <div className="flex-1 min-w-0">
            <label className="block text-[10px] font-bold uppercase text-slate-400">
              Fecha y Hora de la Prueba
            </label>
            <input
              type="datetime-local"
              value={formData.timestamp}
              onChange={(e) => handleChange('timestamp', e.target.value)}
              className="w-full bg-transparent text-xs font-semibold text-slate-200 focus:outline-none"
            />
          </div>
        </div>

        <div className="glass-panel p-3.5 rounded-2xl border border-marine-800 bg-marine-900/60 flex items-center gap-2.5">
          <FileText className="w-4 h-4 text-cyan-400 shrink-0" />
          <div className="flex-1 min-w-0">
            <label className="block text-[10px] font-bold uppercase text-slate-400">
              Observaciones / Test Kit
            </label>
            <input
              type="text"
              value={formData.notes}
              onChange={(e) => handleChange('notes', e.target.value)}
              placeholder="Ej. Hanna Checker, Salifert, Tropic Marin..."
              className="w-full bg-transparent text-xs font-semibold text-slate-200 focus:outline-none placeholder:text-slate-500"
            />
          </div>
        </div>
      </div>

      {/* Botón de Guardado Rápido con Confirmación Visual Táctil */}
      <div className="pt-2 flex items-center gap-3">
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="btn-touch-secondary flex-1 sm:flex-none"
          >
            Cancelar
          </button>
        )}

        <button
          type="submit"
          disabled={loading || successStatus}
          className={`btn-touch flex-1 font-black text-sm sm:text-base transition-all ${
            successStatus
              ? 'bg-gradient-to-r from-emerald-500 to-emerald-400 text-marine-950 shadow-neon-emerald scale-[1.02]'
              : 'bg-gradient-to-r from-cyan-500 via-cyan-400 to-emerald-400 hover:from-cyan-400 hover:to-emerald-300 text-marine-950 shadow-neon-cyan active:scale-95'
          } ${loading ? 'opacity-70 cursor-wait' : ''}`}
        >
          {successStatus ? (
            <>
              <CheckCircle2 className="w-6 h-6 stroke-[3] animate-bounce" />
              <span>¡Mediciones Registradas con Éxito!</span>
            </>
          ) : loading ? (
            <>
              <div className="w-5 h-5 border-2 border-marine-950 border-t-transparent rounded-full animate-spin" />
              <span>Guardando Mediciones...</span>
            </>
          ) : (
            <>
              <Check className="w-6 h-6 stroke-[3]" />
              <span>Registrar Mediciones</span>
            </>
          )}
        </button>
      </div>

      {/* Modal de Cámara y Escaneo Visual con IA */}
      <CameraScannerModal
        isOpen={isScannerOpen}
        onClose={() => setIsScannerOpen(false)}
        onScanComplete={handleScanComplete}
        preferredParameter={activeScanParam}
      />
    </form>
  );
}
