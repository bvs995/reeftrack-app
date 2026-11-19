import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
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
  Camera,
  ChevronDown,
  ChevronUp,
  FlaskConical,
  Info
} from 'lucide-react';
import { saveMeasurement, fetchMeasurements } from '../api';
import CameraScannerModal from './CameraScannerModal';
import { getMarineProfile } from '../utils/marineProfiles';

export default function QuickEntryForm({
  tank = null,
  tankId = null,
  onSuccess,
  onCancel,
  initialLastMeasurement = null
}) {
  const { t } = useTranslation();

  const [formData, setFormData] = useState({
    // Básicos
    salinity_ppt: '',
    salinity: '',
    temperature: '',
    temperatura: '',
    ph: '',
    ammonia_ppm: '',
    ammonia: '',
    nitrite_ppm: '',
    nitrite: '',

    // Macros & Nutrientes
    alkalinity_dkh: '',
    kh: '',
    calcium_ppm: '',
    calcium: '',
    magnesium_ppm: '',
    magnesium: '',
    nitrate_ppm: '',
    nitrate: '',
    phosphate_ppm: '',
    phosphate: '',

    // Dulce
    gh_dgh: '',

    // Metadata
    notes: '',
    timestamp: new Date().toISOString().slice(0, 16)
  });

  // Métodos de medición para KH y PO4
  const [testMethods, setTestMethods] = useState({
    kh: 'drop_kit',
    po4: 'drop_kit'
  });

  // Elementos traza
  const [traceElements, setTraceElements] = useState({
    k: '',
    sr: '',
    i: '',
    fe: ''
  });

  const [showTraceElements, setShowTraceElements] = useState(false);
  const [lastMeasurement, setLastMeasurement] = useState(initialLastMeasurement);
  const [loading, setLoading] = useState(false);
  const [successStatus, setSuccessStatus] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);

  // Estados para captura y escaneo visual por cámara
  const [isScannerOpen, setIsScannerOpen] = useState(false);
  const [activeScanParam, setActiveScanParam] = useState(null);
  const [scannedHighlight, setScannedHighlight] = useState(null);

  // Detección del tipo de agua y perfil marino
  const tankTypeNormalized = (tank?.tank_type || tank?.tipoAgua || tank?.type || '').toLowerCase();
  const isDulce = ['dulce', 'plantado', 'freshwater'].some(t => tankTypeNormalized.includes(t));
  const isMarine = !isDulce;
  const reefProfileKey = tank?.reef_profile || (tankTypeNormalized === 'marine_fish' ? 'fowlr_soft' : 'lps_reef');
  const profileInfo = getMarineProfile(reefProfileKey);

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
    setFormData(prev => {
      const next = { ...prev, [field]: val };
      if (field === 'temperature' || field === 'temperatura') {
        next.temperature = val;
        next.temperatura = val;
      }
      if (field === 'kh' || field === 'alkalinity_dkh') {
        next.kh = val;
        next.alkalinity_dkh = val;
      }
      if (field === 'calcium' || field === 'calcium_ppm') {
        next.calcium = val;
        next.calcium_ppm = val;
      }
      if (field === 'magnesium' || field === 'magnesium_ppm') {
        next.magnesium = val;
        next.magnesium_ppm = val;
      }
      if (field === 'nitrate' || field === 'nitrate_ppm') {
        next.nitrate = val;
        next.nitrate_ppm = val;
      }
      if (field === 'phosphate' || field === 'phosphate_ppm') {
        next.phosphate = val;
        next.phosphate_ppm = val;
      }
      if (field === 'salinity' || field === 'salinity_ppt') {
        next.salinity = val;
        next.salinity_ppt = val;
      }
      if (field === 'ammonia' || field === 'ammonia_ppm') {
        next.ammonia = val;
        next.ammonia_ppm = val;
      }
      if (field === 'nitrite' || field === 'nitrite_ppm') {
        next.nitrite = val;
        next.nitrite_ppm = val;
      }
      return next;
    });
  };

  const handleTraceChange = (element, val) => {
    setTraceElements(prev => ({
      ...prev,
      [element]: val
    }));
  };

  const handleScanComplete = (result) => {
    if (result && result.parameter && result.value !== null && result.value !== undefined) {
      const pKey = result.parameter;
      const strVal = String(result.value);

      setFormData(prev => {
        const next = {
          ...prev,
          [pKey]: strVal,
          notes: result.kit_detected
            ? (prev.notes ? `${prev.notes} | ${result.kit_detected}` : result.kit_detected)
            : prev.notes
        };
        if (pKey === 'alkalinity_dkh') next.kh = strVal;
        if (pKey === 'calcium_ppm') next.calcium = strVal;
        if (pKey === 'magnesium_ppm') next.magnesium = strVal;
        if (pKey === 'nitrate_ppm') next.nitrate = strVal;
        if (pKey === 'phosphate_ppm') next.phosphate = strVal;
        if (pKey === 'salinity_ppt') next.salinity = strVal;
        if (pKey === 'temperature') next.temperatura = strVal;
        return next;
      });

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

  const parseNumOrNull = (val) => {
    if (val === '' || val === null || val === undefined) return null;
    const n = parseFloat(val);
    return isNaN(n) ? null : n;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage(null);

    const khVal = parseNumOrNull(formData.kh || formData.alkalinity_dkh);
    const caVal = parseNumOrNull(formData.calcium || formData.calcium_ppm);
    const mgVal = parseNumOrNull(formData.magnesium || formData.magnesium_ppm);
    const no3Val = parseNumOrNull(formData.nitrate || formData.nitrate_ppm);
    const po4Val = parseNumOrNull(formData.phosphate || formData.phosphate_ppm);
    const salVal = parseNumOrNull(formData.salinity || formData.salinity_ppt);
    const tempVal = parseNumOrNull(formData.temperature || formData.temperatura);
    const phVal = parseNumOrNull(formData.ph);
    const nh3Val = parseNumOrNull(formData.ammonia || formData.ammonia_ppm);
    const no2Val = parseNumOrNull(formData.nitrite || formData.nitrite_ppm);
    const ghVal = parseNumOrNull(formData.gh_dgh);

    const kVal = parseNumOrNull(traceElements.k);
    const srVal = parseNumOrNull(traceElements.sr);
    const iVal = parseNumOrNull(traceElements.i);
    const feVal = parseNumOrNull(traceElements.fe);

    // Preparar trace_elements solo con los elementos introducidos
    const tracePayload = {};
    if (kVal !== null) tracePayload.k = kVal;
    if (srVal !== null) tracePayload.sr = srVal;
    if (iVal !== null) tracePayload.i = iVal;
    if (feVal !== null) tracePayload.fe = feVal;

    const fieldsToSubmit = {
      ph: phVal,
      salinity: salVal,
      salinity_ppt: salVal,
      temperature: tempVal,
      temperatura: tempVal,
      ammonia: nh3Val,
      ammonia_ppm: nh3Val,
      nitrite: no2Val,
      nitrite_ppm: no2Val,
      kh: khVal,
      alkalinity_dkh: khVal,
      calcium: caVal,
      calcium_ppm: caVal,
      magnesium: mgVal,
      magnesium_ppm: mgVal,
      nitrate: no3Val,
      nitrate_ppm: no3Val,
      phosphate: po4Val,
      phosphate_ppm: po4Val,
      gh_dgh: ghVal,
      test_methods: isMarine ? {
        po4: testMethods.po4 || 'drop_kit',
        kh: testMethods.kh || 'drop_kit'
      } : null,
      trace_elements: (isMarine && Object.keys(tracePayload).length > 0) ? tracePayload : null
    };

    // Validar que al menos un campo numérico contenga información
    const hasValue = Object.entries(fieldsToSubmit).some(([k, v]) => {
      if (k === 'test_methods' || k === 'trace_elements') return false;
      return typeof v === 'number' && !isNaN(v);
    }) || Object.keys(tracePayload).length > 0;

    if (!hasValue) {
      setErrorMessage(t('quickEntry.emptyError') || 'Por favor ingresa al menos un parámetro numérico.');
      triggerHaptic([50, 50, 50]);
      return;
    }

    if (formData.notes?.trim()) {
      fieldsToSubmit.notes = formData.notes.trim();
    }

    if (formData.timestamp) {
      fieldsToSubmit.timestamp = new Date(formData.timestamp).toISOString();
    }

    const targetTankId = tank?.id || tankId;
    if (targetTankId) {
      fieldsToSubmit.tank_id = targetTankId;
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
          salinity_ppt: '',
          salinity: '',
          temperature: '',
          temperatura: '',
          ph: '',
          ammonia_ppm: '',
          ammonia: '',
          nitrite_ppm: '',
          nitrite: '',
          alkalinity_dkh: '',
          kh: '',
          calcium_ppm: '',
          calcium: '',
          magnesium_ppm: '',
          magnesium: '',
          nitrate_ppm: '',
          nitrate: '',
          phosphate_ppm: '',
          phosphate: '',
          gh_dgh: '',
          notes: ''
        }));
        setTraceElements({ k: '', sr: '', i: '', fe: '' });
        if (onSuccess) onSuccess(saved);
      }, 1200);

    } catch (err) {
      setErrorMessage(err.message || 'Error al guardar la medición');
      triggerHaptic([80, 50, 80]);
    } finally {
      setLoading(false);
    }
  };

  // Helper para renderizar input de parámetro individual
  const renderParamInput = ({
    key,
    label,
    unit,
    step,
    min,
    max,
    placeholder,
    safeRange,
    value,
    onChange,
    lastVal,
    methodSelector = null
  }) => {
    const isHighlighted = scannedHighlight?.parameter === key;

    return (
      <div
        key={key}
        className={`rounded-xl p-3 bg-slate-900/80 border transition-all flex flex-col justify-between ${
          isHighlighted
            ? 'border-cyan-400 ring-2 ring-cyan-400/30 shadow-[0_0_15px_rgba(0,242,254,0.25)]'
            : 'border-cyan-500/30 hover:border-cyan-500/60'
        }`}
      >
        <div className="flex items-center justify-between gap-1.5 mb-2">
          <div className="flex items-center gap-1.5 min-w-0">
            <label className="block text-xs font-semibold text-cyan-300 uppercase tracking-wider truncate">
              {label} {unit ? `(${unit})` : ''}
            </label>
            <button
              type="button"
              onClick={() => openScanner(key)}
              className="p-1 rounded text-slate-400 hover:text-cyan-300 hover:bg-slate-800 transition-colors"
              title={`Escanear foto para ${label}`}
            >
              <Camera className="w-3 h-3" />
            </button>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            {methodSelector}
            {safeRange && (
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-cyan-950/60 text-cyan-300 border border-cyan-500/30">
                {safeRange}
              </span>
            )}
          </div>
        </div>

        <div className="relative flex items-center">
          <input
            type="number"
            step={step}
            min={min}
            max={max}
            inputMode="decimal"
            placeholder={placeholder}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className="w-full px-3 py-2 bg-slate-950/90 border border-cyan-500/30 rounded-lg text-white font-bold placeholder-slate-500 focus:outline-none focus:border-cyan-400 shadow-inner"
          />
          {unit && (
            <span className="absolute right-3 text-xs font-extrabold text-cyan-400/80 pointer-events-none select-none">
              {unit}
            </span>
          )}
        </div>

        <div className="mt-2 flex items-center justify-between text-[11px] text-slate-400 select-none">
          <span className="font-medium">{t('common.lastReading')}:</span>
          <span className="font-bold text-slate-300 bg-slate-950 px-1.5 py-0.5 rounded border border-slate-800">
            {lastVal !== null && lastVal !== undefined ? `${lastVal} ${unit}` : t('common.noPriorRecord')}
          </span>
        </div>
      </div>
    );
  };

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
              <span>{t('quickEntry.cameraBannerTitle') || 'Captura de Parámetros con Cámara'}</span>
              <span className="text-[10px] font-bold px-1.5 py-0.2 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/30 flex items-center gap-1">
                <Sparkles className="w-2.5 h-2.5" /> IA Vision
              </span>
              {isMarine && (
                <span className="text-[10px] font-bold px-1.5 py-0.2 rounded-full bg-blue-500/10 text-blue-300 border border-blue-500/30">
                  {profileInfo.name}
                </span>
              )}
            </div>
            <div className="text-[11px] text-slate-400">
              {t('quickEntry.cameraBannerDesc') || 'Fotografía tu vial de test o fotómetro y la IA extraerá el valor automáticamente.'}
            </div>
          </div>
        </div>

        <button
          type="button"
          onClick={() => openScanner(null)}
          className="btn-touch py-2.5 px-4 bg-gradient-to-r from-cyan-500 via-cyan-400 to-emerald-400 hover:from-cyan-400 hover:to-emerald-300 text-marine-950 font-black text-xs rounded-xl shadow-neon-cyan active:scale-95 flex items-center justify-center gap-2"
        >
          <Camera className="w-4 h-4 stroke-[2.5]" />
          <span>{t('quickEntry.scanButton') || 'Escanear Test'}</span>
        </button>
      </div>

      {/* Banner de confirmación de lectura autocompletada por IA */}
      {scannedHighlight && (
        <div className="p-3.5 rounded-2xl bg-cyan-500/15 border border-cyan-500/50 text-cyan-200 text-xs font-semibold flex items-center justify-between gap-2 animate-in fade-in slide-in-from-top-2 shadow-lg">
          <div className="flex items-center gap-2.5 min-w-0">
            <Sparkles className="w-5 h-5 text-cyan-400 shrink-0 animate-pulse" />
            <div className="min-w-0">
              <div className="font-extrabold text-white text-xs truncate">
                {t('quickEntry.detectedParam', { val: scannedHighlight.value }) || `Detectado: ${scannedHighlight.value}`}
              </div>
              <div className="text-[11px] text-slate-300">
                {t('quickEntry.detectedDesc') || 'Valor verificado e insertado en el formulario.'}
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
            title={t('common.close')}
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

      {/* RENDERIZADO CONDICIONAL: AGUA DULCE vs MARINO */}
      {isDulce ? (
        /* VISTA AGUA DULCE / PLANTADO */
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
          {renderParamInput({
            key: 'ph',
            label: 'pH',
            unit: '',
            step: '0.01',
            min: '6.0',
            max: '8.5',
            placeholder: '6.8',
            safeRange: '6.5 - 7.5',
            value: formData.ph,
            onChange: (v) => handleChange('ph', v),
            lastVal: lastMeasurement?.ph
          })}
          {renderParamInput({
            key: 'temperature',
            label: 'Temperatura',
            unit: '°C',
            step: '0.1',
            min: '15',
            max: '35',
            placeholder: '25.5',
            safeRange: '24.0 - 26.5 °C',
            value: formData.temperature,
            onChange: (v) => handleChange('temperature', v),
            lastVal: lastMeasurement?.temperature || lastMeasurement?.temperatura
          })}
          {renderParamInput({
            key: 'ammonia',
            label: 'Amoníaco (NH3)',
            unit: 'ppm',
            step: '0.01',
            min: '0.0',
            max: '5.0',
            placeholder: '0.0',
            safeRange: '< 0.02 ppm',
            value: formData.ammonia,
            onChange: (v) => handleChange('ammonia', v),
            lastVal: lastMeasurement?.ammonia || lastMeasurement?.ammonia_ppm
          })}
          {renderParamInput({
            key: 'nitrite',
            label: 'Nitrito (NO2)',
            unit: 'ppm',
            step: '0.01',
            min: '0.0',
            max: '5.0',
            placeholder: '0.0',
            safeRange: '< 0.05 ppm',
            value: formData.nitrite,
            onChange: (v) => handleChange('nitrite', v),
            lastVal: lastMeasurement?.nitrite || lastMeasurement?.nitrite_ppm
          })}
          {renderParamInput({
            key: 'nitrate',
            label: 'Nitrato (NO3)',
            unit: 'ppm',
            step: '0.5',
            min: '0',
            max: '80',
            placeholder: '10.0',
            safeRange: '5.0 - 25.0 ppm',
            value: formData.nitrate,
            onChange: (v) => handleChange('nitrate', v),
            lastVal: lastMeasurement?.nitrate || lastMeasurement?.nitrate_ppm
          })}
          {renderParamInput({
            key: 'gh_dgh',
            label: 'Dureza General (GH)',
            unit: 'dGH',
            step: '0.5',
            min: '0',
            max: '30',
            placeholder: '6.0',
            safeRange: '4.0 - 10.0 dGH',
            value: formData.gh_dgh,
            onChange: (v) => handleChange('gh_dgh', v),
            lastVal: lastMeasurement?.gh_dgh
          })}
        </div>
      ) : (
        /* VISTA MARINA: 3 SECCIONES ESTRUCTURADAS */
        <div className="space-y-5">
          {/* SECCIÓN 1: PARÁMETROS BÁSICOS Y CONDICIONES FÍSICAS */}
          <div className="rounded-2xl border border-cyan-500/20 bg-slate-950/40 p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-cyan-500/20 pb-2">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-cyan-400"></span>
                <h4 className="text-xs font-black uppercase tracking-wider text-cyan-300">
                  1. Básicos & Físicos
                </h4>
              </div>
              <span className="text-[10px] text-slate-400 font-semibold">
                Salinidad, Temp, pH, Amoníaco y Nitrito
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {renderParamInput({
                key: 'salinity',
                label: 'Salinidad',
                unit: 'SG',
                step: '0.001',
                min: '1.018',
                max: '1.030',
                placeholder: '1.025',
                safeRange: `${profileInfo.targets.salinity.min} - ${profileInfo.targets.salinity.max} SG`,
                value: formData.salinity,
                onChange: (v) => handleChange('salinity', v),
                lastVal: lastMeasurement?.salinity || lastMeasurement?.salinity_ppt
              })}

              {renderParamInput({
                key: 'temperature',
                label: 'Temperatura',
                unit: '°C',
                step: '0.1',
                min: '15',
                max: '35',
                placeholder: '25.5',
                safeRange: `${profileInfo.targets.temperature.min} - ${profileInfo.targets.temperature.max} °C`,
                value: formData.temperature,
                onChange: (v) => handleChange('temperature', v),
                lastVal: lastMeasurement?.temperature || lastMeasurement?.temperatura
              })}

              {renderParamInput({
                key: 'ph',
                label: 'pH',
                unit: '',
                step: '0.01',
                min: '6.0',
                max: '9.0',
                placeholder: '8.2',
                safeRange: `${profileInfo.targets.ph.min} - ${profileInfo.targets.ph.max}`,
                value: formData.ph,
                onChange: (v) => handleChange('ph', v),
                lastVal: lastMeasurement?.ph
              })}

              {renderParamInput({
                key: 'ammonia',
                label: 'Amoníaco (NH3)',
                unit: 'ppm',
                step: '0.01',
                min: '0.00',
                max: '5.00',
                placeholder: '0.00',
                safeRange: '0.00 ppm',
                value: formData.ammonia,
                onChange: (v) => handleChange('ammonia', v),
                lastVal: lastMeasurement?.ammonia || lastMeasurement?.ammonia_ppm
              })}

              {renderParamInput({
                key: 'nitrite',
                label: 'Nitrito (NO2)',
                unit: 'ppm',
                step: '0.01',
                min: '0.00',
                max: '5.00',
                placeholder: '0.00',
                safeRange: '0.00 ppm',
                value: formData.nitrite,
                onChange: (v) => handleChange('nitrite', v),
                lastVal: lastMeasurement?.nitrite || lastMeasurement?.nitrite_ppm
              })}
            </div>
          </div>

          {/* SECCIÓN 2: MACROMINERALES & NUTRIENTES */}
          <div className="rounded-2xl border border-cyan-500/20 bg-slate-950/40 p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-cyan-500/20 pb-2">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                <h4 className="text-xs font-black uppercase tracking-wider text-emerald-300">
                  2. Macrominerales & Nutrientes
                </h4>
              </div>
              <span className="text-[10px] text-slate-400 font-semibold">
                KH, Calcio, Magnesio, Nitratos y Fosfatos
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {renderParamInput({
                key: 'kh',
                label: 'Alcalinidad (KH)',
                unit: 'dKH',
                step: '0.1',
                min: '4.0',
                max: '16.0',
                placeholder: '8.5',
                safeRange: `${profileInfo.targets.kh.min} - ${profileInfo.targets.kh.max} dKH`,
                value: formData.kh,
                onChange: (v) => handleChange('kh', v),
                lastVal: lastMeasurement?.kh || lastMeasurement?.alkalinity_dkh,
                methodSelector: (
                  <select
                    value={testMethods.kh}
                    onChange={(e) => setTestMethods(prev => ({ ...prev, kh: e.target.value }))}
                    className="text-[10px] bg-slate-950 border border-cyan-500/40 rounded px-1.5 py-0.5 text-cyan-300 font-bold focus:outline-none"
                    title="Método de test para KH"
                  >
                    <option value="drop_kit">Gotas</option>
                    <option value="photometer_ulr">Fotómetro</option>
                    <option value="icp">Test ICP</option>
                  </select>
                )
              })}

              {renderParamInput({
                key: 'calcium',
                label: 'Calcio (Ca)',
                unit: 'ppm',
                step: '1',
                min: '200',
                max: '600',
                placeholder: '420',
                safeRange: `${profileInfo.targets.calcium.min} - ${profileInfo.targets.calcium.max} ppm`,
                value: formData.calcium,
                onChange: (v) => handleChange('calcium', v),
                lastVal: lastMeasurement?.calcium || lastMeasurement?.calcium_ppm
              })}

              {renderParamInput({
                key: 'magnesium',
                label: 'Magnesio (Mg)',
                unit: 'ppm',
                step: '1',
                min: '800',
                max: '1800',
                placeholder: '1350',
                safeRange: `${profileInfo.targets.magnesium.min} - ${profileInfo.targets.magnesium.max} ppm`,
                value: formData.magnesium,
                onChange: (v) => handleChange('magnesium', v),
                lastVal: lastMeasurement?.magnesium || lastMeasurement?.magnesium_ppm
              })}

              {renderParamInput({
                key: 'nitrate',
                label: 'Nitrato (NO3)',
                unit: 'ppm',
                step: '0.1',
                min: '0.0',
                max: '100.0',
                placeholder: '5.0',
                safeRange: `${profileInfo.targets.nitrate.min} - ${profileInfo.targets.nitrate.max} ppm`,
                value: formData.nitrate,
                onChange: (v) => handleChange('nitrate', v),
                lastVal: lastMeasurement?.nitrate || lastMeasurement?.nitrate_ppm
              })}

              {renderParamInput({
                key: 'phosphate',
                label: 'Fosfato (PO4)',
                unit: 'ppm',
                step: '0.001',
                min: '0.000',
                max: '2.000',
                placeholder: '0.035',
                safeRange: `${profileInfo.targets.phosphate.min} - ${profileInfo.targets.phosphate.max} ppm`,
                value: formData.phosphate,
                onChange: (v) => handleChange('phosphate', v),
                lastVal: lastMeasurement?.phosphate || lastMeasurement?.phosphate_ppm,
                methodSelector: (
                  <select
                    value={testMethods.po4}
                    onChange={(e) => setTestMethods(prev => ({ ...prev, po4: e.target.value }))}
                    className="text-[10px] bg-slate-950 border border-cyan-500/40 rounded px-1.5 py-0.5 text-cyan-300 font-bold focus:outline-none"
                    title="Método de test para Fosfatos"
                  >
                    <option value="drop_kit">Gotas</option>
                    <option value="photometer_ulr">Fotómetro ULR</option>
                    <option value="icp">Test ICP</option>
                  </select>
                )
              })}
            </div>
          </div>

          {/* SECCIÓN 3: ELEMENTOS TRAZA (COLAPSABLE PARA LPS/SPS) */}
          <div className="rounded-2xl border border-cyan-500/20 bg-slate-950/40 overflow-hidden transition-all">
            <button
              type="button"
              onClick={() => setShowTraceElements(!showTraceElements)}
              className="w-full p-4 flex items-center justify-between text-left hover:bg-slate-900/60 transition-colors"
            >
              <div className="flex items-center gap-2.5">
                <div className="w-7 h-7 rounded-lg bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 flex items-center justify-center">
                  <FlaskConical className="w-4 h-4" />
                </div>
                <div>
                  <div className="text-xs font-black uppercase tracking-wider text-cyan-300 flex items-center gap-2">
                    <span>3. Elementos Traza / Oligoelementos</span>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                      Opcional (LPS / SPS)
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400">
                    Potasio (K), Estroncio (Sr), Yodo (I) y Hierro (Fe)
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 text-cyan-400">
                <span className="text-xs font-bold">{showTraceElements ? 'Ocultar' : 'Desplegar'}</span>
                {showTraceElements ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </div>
            </button>

            {showTraceElements && (
              <div className="p-4 border-t border-cyan-500/20 bg-slate-900/40 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
                {renderParamInput({
                  key: 'trace_k',
                  label: 'Potasio (K)',
                  unit: 'ppm',
                  step: '1',
                  min: '200',
                  max: '600',
                  placeholder: '400',
                  safeRange: '380 - 410 ppm',
                  value: traceElements.k,
                  onChange: (v) => handleTraceChange('k', v),
                  lastVal: lastMeasurement?.trace_elements?.k
                })}

                {renderParamInput({
                  key: 'trace_sr',
                  label: 'Estroncio (Sr)',
                  unit: 'ppm',
                  step: '0.1',
                  min: '0.0',
                  max: '20.0',
                  placeholder: '8.5',
                  safeRange: '8.0 - 10.0 ppm',
                  value: traceElements.sr,
                  onChange: (v) => handleTraceChange('sr', v),
                  lastVal: lastMeasurement?.trace_elements?.sr
                })}

                {renderParamInput({
                  key: 'trace_i',
                  label: 'Yodo (I)',
                  unit: 'ppm',
                  step: '0.01',
                  min: '0.00',
                  max: '0.20',
                  placeholder: '0.05',
                  safeRange: '0.03 - 0.06 ppm',
                  value: traceElements.i,
                  onChange: (v) => handleTraceChange('i', v),
                  lastVal: lastMeasurement?.trace_elements?.i
                })}

                {renderParamInput({
                  key: 'trace_fe',
                  label: 'Hierro (Fe)',
                  unit: 'ppm',
                  step: '0.001',
                  min: '0.000',
                  max: '0.050',
                  placeholder: '0.002',
                  safeRange: '0.001 - 0.005 ppm',
                  value: traceElements.fe,
                  onChange: (v) => handleTraceChange('fe', v),
                  lastVal: lastMeasurement?.trace_elements?.fe
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Fila compacta opcional: Fecha y Notas del Kit */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
        <div className="glass-panel p-3.5 rounded-2xl border border-marine-800 bg-marine-900/60 flex items-center gap-2.5">
          <Calendar className="w-4 h-4 text-cyan-400 shrink-0" />
          <div className="flex-1 min-w-0">
            <label className="block text-[10px] font-bold uppercase text-slate-400">
              {t('quickEntry.testDate') || 'Fecha y Hora'}
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
              {t('quickEntry.notesLabel') || 'Notas del Test'}
            </label>
            <input
              type="text"
              value={formData.notes}
              onChange={(e) => handleChange('notes', e.target.value)}
              placeholder={t('quickEntry.notesPlaceholder') || 'Observaciones, fotómetro utilizado, etc.'}
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
            {t('common.cancel') || 'Cancelar'}
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
              <span>{t('quickEntry.successBtn') || '¡Medición Guardada!'}</span>
            </>
          ) : loading ? (
            <>
              <div className="w-5 h-5 border-2 border-marine-950 border-t-transparent rounded-full animate-spin" />
              <span>{t('quickEntry.savingBtn') || 'Guardando...'}</span>
            </>
          ) : (
            <>
              <Check className="w-6 h-6 stroke-[3]" />
              <span>{t('quickEntry.submitBtn') || 'Registrar Medición'}</span>
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
