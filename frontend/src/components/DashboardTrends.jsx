import React, { useState, useEffect, useMemo, useRef } from 'react';
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
import annotationPlugin from 'chartjs-plugin-annotation';
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
import { fetchPredictions, fetchMeasurements, fetchPredictiveAnalysis } from '../api';
import { getProfileConfig, getMarineProfile, AQUARIUM_TYPES } from '../utils/marineProfiles';

// Registrar plugins requeridos de Chart.js incluyendo annotationPlugin oficial
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
  onOpenWaterChange = null,
  initialParam = 'fosfatos',
  activeTank = null,
  acuarioActual: propAcuarioActual = null
}) {
  const { t, i18n } = useTranslation();
  const [predictions, setPredictions] = useState(propPredictions);
  const [measurements, setMeasurements] = useState(propMeasurements || []);
  const [loading, setLoading] = useState(!propPredictions);
  const [mostrarDiagnosticoIA, setMostrarDiagnosticoIA] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiAnalysis, setAiAnalysis] = useState(null);
  const [userSelectedEcosystem, setUserSelectedEcosystem] = useState(null);
  const [showTraceElements, setShowTraceElements] = useState(false);

  // 6 Opciones Canónicas de Perfiles para la Barra de Tendencias
  const TRENDS_PROFILES = [
    { id: 'sps_reef', label: '🪸 Arrecife SPS', key: 'sps_reef' },
    { id: 'lps_reef', label: '🪸 Arrecife LPS', key: 'lps_reef' },
    { id: 'mixed_reef', label: '🌊 Mixto', key: 'mixed_reef' },
    { id: 'fish_only', label: '🐠 Peces Marinos', key: 'fish_only' },
    { id: 'planted', label: '🌿 Plantado', key: 'planted' },
    { id: 'freshwater', label: '🐟 Dulce Peces', key: 'freshwater' }
  ];

  // Normalización del ecosistema del acuario según perfil unificado
  const rawTank = propAcuarioActual || activeTank || {};
  const effectiveTank = userSelectedEcosystem
    ? {
        ...rawTank,
        tank_type: userSelectedEcosystem,
        reef_profile: ['fish_only', 'mixed_reef', 'lps_reef', 'sps_reef'].includes(userSelectedEcosystem)
          ? userSelectedEcosystem
          : null
      }
    : rawTank;
  const profileConfig = getProfileConfig(effectiveTank);
  const esAguaSalada = profileConfig.isMarine;
  const activeMarineProfile = profileConfig;
  const visibleFields = profileConfig.visibleFields || {};

  const currentTipo = profileConfig.id;
  const acuarioActual = {
    ...rawTank,
    tipo: currentTipo,
    tipoAgua: esAguaSalada ? 'salada' : 'dulce'
  };

  // Listas maestras de parámetros especializadas por perfil
  const parametrosFishOnly = [
    { id: 'salinidad', key: 'salinity', nombre: 'Salinidad', unidad: '(SG / ppt)' },
    { id: 'temperatura', key: 'temperature', nombre: 'Temperatura', unidad: '(°C)' },
    { id: 'ph', key: 'ph', nombre: 'pH', unidad: '' },
    { id: 'nitratos', key: 'nitrate', nombre: 'Nitratos', unidad: '(NO3 ppm)' },
    { id: 'fosfatos', key: 'phosphate', nombre: 'Fosfatos', unidad: '(PO4 ppm)' },
    { id: 'amoniaco', key: 'ammonia', nombre: 'Amoníaco', unidad: '(NH3)' },
    { id: 'nitritos', key: 'nitrite', nombre: 'Nitritos', unidad: '(NO2)' },
    { id: 'alcalinidad', key: 'kh', nombre: 'Alcalinidad', unidad: '(dKH - opcional)' }
  ];

  const parametrosReefBasicos = [
    { id: 'salinidad', key: 'salinity', nombre: 'Salinidad', unidad: '(SG / ppt)' },
    { id: 'temperatura', key: 'temperature', nombre: 'Temperatura', unidad: '(°C)' },
    { id: 'ph', key: 'ph', nombre: 'pH', unidad: '' },
    { id: 'alcalinidad', key: 'kh', nombre: 'Alcalinidad', unidad: '(dKH)' },
    { id: 'calcio', key: 'calcium', nombre: 'Calcio', unidad: '(Ca ppm)' },
    { id: 'magnesio', key: 'magnesium', nombre: 'Magnesio', unidad: '(Mg ppm)' },
    { id: 'nitratos', key: 'nitrate', nombre: 'Nitratos', unidad: '(NO3 ppm)' },
    { id: 'fosfatos', key: 'phosphate', nombre: 'Fosfatos', unidad: '(PO4 ppm)' },
    { id: 'amoniaco', key: 'ammonia', nombre: 'Amoníaco', unidad: '(NH3)' },
    { id: 'nitritos', key: 'nitrite', nombre: 'Nitritos', unidad: '(NO2)' }
  ];

  const parametrosTraza = [
    { id: 'potasio', key: 'potassium', nombre: 'Potasio', unidad: '(K ppm)' },
    { id: 'estroncio', key: 'strontium', nombre: 'Estroncio', unidad: '(Sr ppm)' },
    { id: 'yodo', key: 'iodine', nombre: 'Yodo', unidad: '(I ppm)' },
    { id: 'hierro', key: 'iron', nombre: 'Hierro', unidad: '(Fe ppm)' }
  ];

  const parametrosDulcePeces = [
    { id: 'ph', key: 'ph', nombre: 'pH', unidad: '' },
    { id: 'temperatura', key: 'temperature', nombre: 'Temperatura', unidad: '(°C)' },
    { id: 'amoniaco', key: 'ammonia', nombre: 'Amoníaco', unidad: '(NH3)' },
    { id: 'nitritos', key: 'nitrite', nombre: 'Nitritos', unidad: '(NO2)' },
    { id: 'nitratos', key: 'nitrate', nombre: 'Nitratos', unidad: '(NO3 ppm)' },
    { id: 'gh', key: 'gh_dgh', nombre: 'Dureza General', unidad: '(GH)' }
  ];

  const parametrosPlantado = [
    { id: 'ph', key: 'ph', nombre: 'pH', unidad: '' },
    { id: 'temperatura', key: 'temperature', nombre: 'Temperatura', unidad: '(°C)' },
    { id: 'alcalinidad', key: 'kh', nombre: 'Alcalinidad', unidad: '(dKH)' },
    { id: 'nitratos', key: 'nitrate', nombre: 'Nitrógeno', unidad: '(NO3 ppm)' },
    { id: 'fosfatos', key: 'phosphate', nombre: 'Fósforo', unidad: '(PO4 ppm)' },
    { id: 'gh', key: 'gh_dgh', nombre: 'Dureza (GH)', unidad: '(dGH)' },
    { id: 'potasio', key: 'potassium', nombre: 'Potasio', unidad: '(K ppm)' },
    { id: 'hierro', key: 'iron', nombre: 'Hierro', unidad: '(Fe ppm)' },
    { id: 'co2', key: 'co2', nombre: 'CO2 disuelto', unidad: '(ppm)' }
  ];

  // Lógica de ruteo estricta según el perfil activo
  let parametrosAMostrar = [];
  if (profileConfig.id === 'fish_only') {
    parametrosAMostrar = parametrosFishOnly;
  } else if (profileConfig.id === 'planted') {
    parametrosAMostrar = parametrosPlantado;
  } else if (profileConfig.id === 'freshwater') {
    parametrosAMostrar = parametrosDulcePeces;
  } else {
    // mixed_reef, lps_reef, sps_reef
    parametrosAMostrar = showTraceElements
      ? [...parametrosReefBasicos, ...parametrosTraza]
      : parametrosReefBasicos;
  }

  const [activeParam, setActiveParam] = useState(() => {
    if (profileConfig.id === 'planted') return 'potasio';
    if (profileConfig.id === 'fish_only') return 'salinidad';
    if (esAguaSalada) return 'alcalinidad';
    return 'ph';
  });

  const parametroActivo = activeParam;
  const setParametroActivo = (id) => {
    triggerHaptic(15);
    setActiveParam(id);
  };

  const handleSelectEcosystem = (newEcosystemId) => {
    triggerHaptic(20);
    setUserSelectedEcosystem(newEcosystemId);
    setAiAnalysis(null);

    // Ajustar parámetro activo inteligentemente según el nuevo perfil
    if (newEcosystemId === 'fish_only') {
      if (['calcio', 'magnesio', 'potasio', 'estroncio', 'yodo', 'hierro', 'gh', 'co2'].includes(activeParam)) {
        setActiveParam('salinidad');
      }
    } else if (newEcosystemId === 'planted') {
      if (['salinidad', 'calcio', 'magnesio', 'estroncio', 'yodo'].includes(activeParam)) {
        setActiveParam('potasio');
      }
    } else if (newEcosystemId === 'freshwater') {
      if (['salinidad', 'alcalinidad', 'calcio', 'magnesio', 'fosfatos', 'potasio', 'estroncio', 'yodo', 'hierro', 'co2'].includes(activeParam)) {
        setActiveParam('ph');
      }
    } else {
      // mixed_reef, lps_reef, sps_reef
      if (['gh', 'co2'].includes(activeParam)) {
        setActiveParam('alcalinidad');
      }
    }
  };

  // Asegurar que el parámetro seleccionado sea coherente con parametrosAMostrar
  useEffect(() => {
    const isCurrentValid = parametrosAMostrar.some(p => p.id === activeParam);
    if (!isCurrentValid && parametrosAMostrar.length > 0) {
      setActiveParam(parametrosAMostrar[0].id);
    }
  }, [profileConfig.id, parametrosAMostrar, activeParam]);

  const triggerHaptic = (ms = 15) => {
    if (typeof navigator !== 'undefined' && navigator.vibrate) {
      navigator.vibrate(ms);
    }
  };

  const handleAnalizarConIA = async () => {
    triggerHaptic(25);
    setMostrarDiagnosticoIA(true);

    if (aiLoading) return;
    setAiLoading(true);
    try {
      const alk = predictions?.alkalinity;
      const cal = predictions?.calcium;
      const wc = predictions?.water_change;
      const pRanges = profileConfig.ranges || {};

      const payload = {
        nombre_acuario: effectiveTank.name || 'Mi Acuario Principal',
        volumen_litros: Number(effectiveTank.volume_liters) || 280,
        tipo: profileConfig.id,
        tank_type: profileConfig.id,
        reef_profile: profileConfig.isMarine ? profileConfig.id : null,
        dosing_method: effectiveTank.dosing_method || (profileConfig.isMarine ? 'water_changes' : null),
        lighting_par: effectiveTank.lighting_par,
        flow_profile: effectiveTank.flow_profile,
        ph: pRanges.ph?.target ?? 8.2,
        kh: alk?.latest_value ?? pRanges.kh?.target ?? 8.2,
        calcio: profileConfig.id === 'fish_only' || !profileConfig.isMarine ? null : (cal?.latest_value ?? pRanges.calcium?.target ?? 420),
        magnesio: profileConfig.id === 'fish_only' || !profileConfig.isMarine ? null : (pRanges.magnesium?.target ?? 1320),
        nitrato: wc?.current_nitrate_ppm ?? pRanges.nitrate?.target ?? 5.0,
        fosfato: pRanges.phosphate?.target ?? 0.04,
        temperatura: pRanges.temperature?.target ?? 25.0,
        salinity: profileConfig.isMarine ? (pRanges.salinity?.target ?? 1.025) : null,
        ammonia: pRanges.ammonia?.target ?? 0.0,
        nitrite: pRanges.nitrite?.target ?? 0.0,
        tendencia_reciente: `Biotipo activo: ${profileConfig.name}. Consumo KH: ${alk?.daily_consumption_rate ? alk.daily_consumption_rate.toFixed(2) + ' dKH/d' : 'Estable'}. Acumulación NO3: ${wc?.daily_accumulation_rate ? wc.daily_accumulation_rate.toFixed(2) + ' ppm/d' : 'Estable'}.`
      };
      const res = await fetchPredictiveAnalysis(payload);
      if (res?.data) {
        setAiAnalysis(res.data);
      }
    } catch (err) {
      console.error('Error al consultar diagnóstico IA:', err);
    } finally {
      setAiLoading(false);
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

  // Parámetros disponibles y sus configuraciones maestras para ambos ecosistemas
  const PARAM_CONFIG = {
    // ---- Parámetros Agua Salada / Arrecife ----
    alcalinidad: {
      key: 'alkalinity_dkh',
      code: 'kh',
      name: 'Alcalinidad (dKH)',
      shortName: 'Alcalinidad',
      unit: 'dKH',
      safeMin: 7.5,
      safeMax: 9.0,
      step: 0.1,
      color: '#00f2fe',
      predictionData: predictions?.alkalinity
    },
    calcio: {
      key: 'calcium_ppm',
      code: 'calcium',
      name: 'Calcio (Ca)',
      shortName: 'Calcio',
      unit: 'ppm',
      safeMin: 400.0,
      safeMax: 450.0,
      step: 1.0,
      color: '#10b981',
      predictionData: predictions?.calcium
    },
    magnesio: {
      key: 'magnesium_ppm',
      code: 'magnesium',
      name: 'Magnesio (Mg)',
      shortName: 'Magnesio',
      unit: 'ppm',
      safeMin: 1280.0,
      safeMax: 1420.0,
      step: 5.0,
      color: '#38bdf8',
      predictionData: null
    },
    salinidad: {
      key: 'salinity_ppt',
      code: 'salinity',
      name: 'Salinidad (SG / ppt)',
      shortName: 'Salinidad',
      unit: 'SG / ppt',
      safeMin: 1.024,
      safeMax: 1.026,
      step: 0.001,
      color: '#0ea5e9',
      predictionData: null
    },
    fosfatos: {
      key: 'phosphate_ppm',
      code: 'phosphate',
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
    nitratos: {
      key: 'nitrate_ppm',
      code: 'nitrate',
      name: 'Nitratos (NO3)',
      shortName: 'Nitratos',
      unit: 'ppm',
      safeMin: 2.0,
      safeMax: 20.0,
      step: 0.1,
      color: '#f59e0b',
      predictionData: predictions?.water_change
    },
    ph: {
      key: 'ph',
      code: 'ph',
      name: 'pH',
      shortName: 'pH',
      unit: '',
      safeMin: 8.0,
      safeMax: 8.3,
      min: 5.5,
      suggestedMax: 8.8,
      step: 0.01,
      color: '#06b6d4',
      predictionData: null
    },
    amoniaco: {
      key: 'ammonia_ppm',
      code: 'ammonia',
      name: 'Amoníaco (NH3)',
      shortName: 'Amoníaco',
      unit: 'ppm',
      safeMin: 0.0,
      safeMax: 0.02,
      min: 0,
      suggestedMax: 0.25,
      step: 0.01,
      color: '#ef4444',
      predictionData: null
    },
    nitritos: {
      key: 'nitrite_ppm',
      code: 'nitrite',
      name: 'Nitritos (NO2)',
      shortName: 'Nitritos',
      unit: 'ppm',
      safeMin: 0.0,
      safeMax: 0.05,
      min: 0,
      suggestedMax: 0.20,
      step: 0.01,
      color: '#f97316',
      predictionData: null
    },
    temperatura: {
      key: 'temperatura',
      code: 'temperature',
      name: 'Temperatura (°C)',
      shortName: 'Temperatura',
      unit: '°C',
      safeMin: 24.0,
      safeMax: 26.0,
      min: 18.0,
      suggestedMax: 32.0,
      step: 0.1,
      color: '#ec4899',
      predictionData: null
    },

    // ---- Elementos Traza (Arrecife & Plantado) ----
    potasio: {
      key: 'potassium_ppm',
      code: 'k',
      name: 'Potasio (K ppm)',
      shortName: 'Potasio',
      unit: 'ppm',
      safeMin: 380.0,
      safeMax: 420.0,
      min: 0,
      suggestedMax: 450.0,
      step: 1.0,
      color: '#10b981',
      predictionData: null
    },
    estroncio: {
      key: 'strontium_ppm',
      code: 'sr',
      name: 'Estroncio (Sr ppm)',
      shortName: 'Estroncio',
      unit: 'ppm',
      safeMin: 8.0,
      safeMax: 10.0,
      min: 0,
      suggestedMax: 15.0,
      step: 0.1,
      color: '#a855f7',
      predictionData: null
    },
    yodo: {
      key: 'iodine_ppm',
      code: 'i',
      name: 'Yodo (I ppm)',
      shortName: 'Yodo',
      unit: 'ppm',
      safeMin: 0.03,
      safeMax: 0.06,
      min: 0,
      suggestedMax: 0.10,
      step: 0.01,
      color: '#eab308',
      predictionData: null
    },
    hierro: {
      key: 'iron_ppm',
      code: 'fe',
      name: 'Hierro (Fe ppm)',
      shortName: 'Hierro',
      unit: 'ppm',
      safeMin: 0.001,
      safeMax: 0.005,
      min: 0,
      suggestedMax: 0.02,
      step: 0.001,
      color: '#f43f5e',
      predictionData: null
    },

    // ---- Parámetros Agua Dulce / Plantado ----
    gh: {
      key: 'gh_dgh',
      code: 'gh_dgh',
      name: 'Dureza General (GH)',
      shortName: 'Dureza General',
      unit: 'dGH',
      safeMin: 4.0,
      safeMax: 10.0,
      min: 0,
      suggestedMax: 15.0,
      step: 0.5,
      color: '#8b5cf6',
      predictionData: null
    },
    kh: {
      key: 'kh',
      code: 'kh',
      name: 'Dureza (KH)',
      shortName: 'KH',
      unit: 'dKH',
      safeMin: 3.0,
      safeMax: 8.0,
      min: 0,
      suggestedMax: 12.0,
      step: 0.5,
      color: '#00f2fe',
      predictionData: null
    },
    co2: {
      key: 'co2_ppm',
      code: 'co2',
      name: 'CO2 disuelto (ppm)',
      shortName: 'CO2',
      unit: 'ppm',
      safeMin: 15.0,
      safeMax: 35.0,
      min: 0,
      suggestedMax: 50.0,
      step: 1.0,
      color: '#38bdf8',
      predictionData: null
    }
  };

  // Sinónimos para mantener compatibilidad con claves en inglés y abreviaturas
  PARAM_CONFIG.dkh = PARAM_CONFIG.alcalinidad;
  PARAM_CONFIG.calcium = PARAM_CONFIG.calcio;
  PARAM_CONFIG.ca = PARAM_CONFIG.calcio;
  PARAM_CONFIG.magnesium = PARAM_CONFIG.magnesio;
  PARAM_CONFIG.mg = PARAM_CONFIG.magnesio;
  PARAM_CONFIG.salinity = PARAM_CONFIG.salinidad;
  PARAM_CONFIG.phosphate = PARAM_CONFIG.fosfatos;
  PARAM_CONFIG.po4 = PARAM_CONFIG.fosfatos;
  PARAM_CONFIG.nitrate = PARAM_CONFIG.nitratos;
  PARAM_CONFIG.no3 = PARAM_CONFIG.nitratos;
  PARAM_CONFIG.temperature = PARAM_CONFIG.temperatura;
  PARAM_CONFIG.temp = PARAM_CONFIG.temperatura;
  PARAM_CONFIG.ammonia = PARAM_CONFIG.amoniaco;
  PARAM_CONFIG.nh3 = PARAM_CONFIG.amoniaco;
  PARAM_CONFIG.nitrite = PARAM_CONFIG.nitritos;
  PARAM_CONFIG.no2 = PARAM_CONFIG.nitritos;
  PARAM_CONFIG.k = PARAM_CONFIG.potasio;
  PARAM_CONFIG.potassium = PARAM_CONFIG.potasio;
  PARAM_CONFIG.sr = PARAM_CONFIG.estroncio;
  PARAM_CONFIG.strontium = PARAM_CONFIG.estroncio;
  PARAM_CONFIG.i = PARAM_CONFIG.yodo;
  PARAM_CONFIG.iodine = PARAM_CONFIG.yodo;
  PARAM_CONFIG.fe = PARAM_CONFIG.hierro;
  PARAM_CONFIG.iron = PARAM_CONFIG.hierro;

  const currentParam = useMemo(() => {
    const base = PARAM_CONFIG[activeParam] || PARAM_CONFIG[parametrosAMostrar[0]?.id] || PARAM_CONFIG.fosfatos;
    const param = { ...base };

    // Buscar el rango correspondiente en profileConfig
    const ranges = profileConfig.ranges || {};
    const traceRanges = profileConfig.traceElements || {};

    let targetRange = null;

    if (['potasio', 'k', 'potassium'].includes(activeParam)) {
      targetRange = traceRanges.k || ranges.potassium;
    } else if (['estroncio', 'sr', 'strontium'].includes(activeParam)) {
      targetRange = traceRanges.sr;
    } else if (['yodo', 'i', 'iodine'].includes(activeParam)) {
      targetRange = traceRanges.i;
    } else if (['hierro', 'fe', 'iron'].includes(activeParam)) {
      targetRange = traceRanges.fe || ranges.iron;
    } else if (['alcalinidad', 'kh', 'dkh'].includes(activeParam)) {
      targetRange = ranges.kh;
    } else if (['calcio', 'calcium', 'ca'].includes(activeParam)) {
      targetRange = ranges.calcium;
    } else if (['magnesio', 'magnesium', 'mg'].includes(activeParam)) {
      targetRange = ranges.magnesium;
    } else if (['salinidad', 'salinity'].includes(activeParam)) {
      targetRange = ranges.salinity;
    } else if (['nitratos', 'nitrate', 'no3'].includes(activeParam)) {
      targetRange = ranges.nitrate;
    } else if (['fosfatos', 'phosphate', 'po4'].includes(activeParam)) {
      targetRange = ranges.phosphate;
    } else if (['temperatura', 'temperature', 'temp'].includes(activeParam)) {
      targetRange = ranges.temperature;
    } else if (activeParam === 'ph') {
      targetRange = ranges.ph;
    } else if (['amoniaco', 'ammonia', 'nh3'].includes(activeParam)) {
      targetRange = ranges.ammonia;
    } else if (['nitritos', 'nitrite', 'no2'].includes(activeParam)) {
      targetRange = ranges.nitrite;
    } else if (['gh', 'gh_dgh'].includes(activeParam)) {
      targetRange = ranges.gh_dgh;
    } else if (['co2', 'co2_ppm'].includes(activeParam)) {
      targetRange = ranges.co2;
    }

    if (targetRange) {
      if (targetRange.min !== undefined && targetRange.min !== null) {
        param.safeMin = targetRange.min;
      }
      if (targetRange.max !== undefined && targetRange.max !== null) {
        param.safeMax = targetRange.max;
      }
      if (targetRange.safeMax !== undefined && targetRange.safeMax !== null) {
        param.safeMax = targetRange.safeMax;
      }
      if (targetRange.step) {
        param.step = Number(targetRange.step);
      }
      if (targetRange.unit !== undefined && targetRange.unit !== '') {
        param.unit = targetRange.unit;
      }
      // Ajustar escala visual suggestedMax
      if (param.safeMax !== undefined) {
        param.suggestedMax = Math.max(
          param.safeMax * 1.25,
          param.suggestedMax || (param.safeMax * 1.15)
        );
      }
    }

    return param;
  }, [activeParam, parametrosAMostrar, profileConfig]);

  // Alertas dinámicas especializadas (Oscilación KH 24h, Nutrientes en cero, Fotómetro ULR)
  const marineAlerts = useMemo(() => {
    if (!esAguaSalada || !measurements || measurements.length === 0) return [];
    const alerts = [];
    const profile = activeMarineProfile;
    const enabledRules = profile?.enabled_rules || {};

    const sorted = [...measurements].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    const latest = sorted[0];

    // 1. Oscilación KH 24h
    if (enabledRules.kh_delta_24h) {
      const latestKh = latest?.kh ?? latest?.alkalinity_dkh;
      const latestTime = latest?.timestamp ? new Date(latest.timestamp).getTime() : 0;

      if (latestKh !== null && latestKh !== undefined) {
        const oneDayAgo = latestTime - 24 * 3600 * 1000;
        const prev24h = sorted.slice(1).find(m => {
          const t = new Date(m.timestamp).getTime();
          const khV = m.kh ?? m.alkalinity_dkh;
          return t >= oneDayAgo && khV !== null && khV !== undefined;
        });

        if (prev24h) {
          const prevKh = prev24h.kh ?? prev24h.alkalinity_dkh;
          const delta = Math.abs(Number(latestKh) - Number(prevKh));
          if (profile.id === 'sps_reef') {
            if (delta >= 0.5) {
              alerts.push({
                type: 'critical',
                title: 'Alerta Crítica: Oscilación Brusca de KH en SPS',
                message: `Variación de ${delta.toFixed(2)} dKH en las últimas 24h (de ${prevKh} a ${latestKh}). Alto riesgo de necrosis tisular rápida o lenta (RTN/STN) en corales SPS.`
              });
            } else if (delta >= 0.3) {
              alerts.push({
                type: 'warning',
                title: 'Advertencia: Inestabilidad de KH en SPS',
                message: `Variación de ${delta.toFixed(2)} dKH en 24h. La estabilidad diaria es vital para SPS; mantén la fluctuación menor a 0.3 dKH.`
              });
            }
          } else if (profile.id === 'mixed_reef') {
            if (delta >= 0.5) {
              alerts.push({
                type: 'critical',
                title: 'Alerta Crítica: Oscilación de KH en Arrecife Mixto',
                message: `Variación de ${delta.toFixed(2)} dKH en 24h (de ${prevKh} a ${latestKh}). Supera el límite de seguridad (0.5 dKH) para corales duros.`
              });
            } else if (delta >= 0.4) {
              alerts.push({
                type: 'warning',
                title: 'Advertencia: Fluctuación de KH en Arrecife Mixto',
                message: `Variación de ${delta.toFixed(2)} dKH en 24h. Límite sugerido de 0.4 dKH/día para balancear blandos, LPS y SPS.`
              });
            }
          } else if (profile.id === 'lps_reef') {
            if (delta >= 0.6) {
              alerts.push({
                type: 'warning',
                title: 'Advertencia: Oscilación de KH en LPS',
                message: `Variación de ${delta.toFixed(2)} dKH en 24h. Se recomienda no exceder 0.6 dKH/día para proteger los pólipos carnosos.`
              });
            }
          } else if (profile.id === 'soft_reef') {
            if (delta >= 1.0) {
              alerts.push({
                type: 'warning',
                title: 'Advertencia: Variación diaria de KH en Corales Blandos',
                message: `Variación de ${delta.toFixed(2)} dKH en 24h. Mantener por debajo de 1.0 dKH/día.`
              });
            }
          }
        }
      }
    }

    // 2. Nutrientes en cero (Piso mínimo)
    if (enabledRules.zero_nutrient_floor && latest) {
      const no3 = latest?.nitrate ?? latest?.nitrate_ppm;
      const po4 = latest?.phosphate ?? latest?.phosphate_ppm;
      const zeroNo3 = no3 !== null && no3 !== undefined && Number(no3) === 0;
      const zeroPo4 = po4 !== null && po4 !== undefined && Number(po4) === 0;

      if (zeroNo3 || zeroPo4) {
        if (profile.id === 'soft_reef') {
          alerts.push({
            type: 'warning',
            title: 'Aviso: Nutrientes en 0.00 ppm',
            message: `Nivel detectado en 0 ppm (${zeroNo3 && zeroPo4 ? 'NO3 y PO4' : zeroNo3 ? 'NO3' : 'PO4'}). Los corales blandos prosperan mejor con nutrientes detectables.`
          });
        } else if (profile.id === 'lps_reef') {
          alerts.push({
            type: 'critical',
            title: 'Alerta de Inanición: Nutrientes en Cero (0.00 ppm)',
            message: `Se detectó ${zeroNo3 && zeroPo4 ? 'NO3 y PO4 en 0.00 ppm' : zeroNo3 ? 'NO3 en 0.00 ppm' : 'PO4 en 0.00 ppm'}. Riesgo inminente de encogimiento y pérdida de tejido en corales LPS por inanición.`
          });
        } else {
          alerts.push({
            type: 'critical',
            title: 'Alerta de Piso Nutricional: Nutrientes en Cero (0.00 ppm)',
            message: `Se detectó ${zeroNo3 && zeroPo4 ? 'NO3 y PO4 en 0.00 ppm' : zeroNo3 ? 'NO3 en 0.00 ppm' : 'PO4 en 0.00 ppm'}. Riesgo inminente de blanqueamiento coralino y brote oportunista de dinoflagelados.`
          });
        }
      }
    }

    // 3. Resolución de Test PO4
    if (enabledRules.test_resolution_po4 && latest) {
      const po4Method = latest?.test_methods?.po4;
      if (po4Method === 'drop_kit') {
        alerts.push({
          type: 'info',
          title: 'Recomendación de Resolución: Fotómetro ULR',
          message: 'Has registrado fosfato con kit de gotas. En acuarios de arrecife sensibles, se recomienda fotómetro digital de rango ultra bajo (ej. Hanna ULR HI774/HI736) o test ICP debido a la baja resolución de las gotas por debajo de 0.05 ppm.'
        });
      }
    }

    // 4. Advertencia de flujo para tejido carnoso LPS
    if (enabledRules.flow_tissue_warning && rawTank?.flow_profile === 'high_turbulent') {
      alerts.push({
        type: 'warning',
        title: 'Precaución de Flujo: Tejido Carnoso LPS',
        message: 'El flujo configurado es muy alto/turbulento. En acuarios con predominancia LPS, un chorro laminar directo puede rasgar o retraer permanentemente el tejido carnoso de Euphyllias y Torch.'
      });
    }

    // 5. Sugerencia de dosificación automatizada
    if (enabledRules.automated_dosing_suggestion && ['water_changes', 'manual_dosing'].includes(rawTank?.dosing_method)) {
      alerts.push({
        type: 'info',
        title: 'Optimización de Estabilidad: Dosificación Automatizada',
        message: 'Para acuarios de arrecife con alta demanda de calcificación, se sugiere migrar a bombas peristálticas (Balling) o reactor de calcio para evitar fluctuaciones bruscas de KH y Ca.'
      });
    }

    return alerts;
  }, [measurements, rawTank, esAguaSalada, activeMarineProfile]);

  // Extractor omnicanal de valores de medición para compatibilidad total
  const getReadingValue = (m, key) => {
    if (!m) return null;
    const isValid = (v) => v !== null && v !== undefined && v !== '' && !isNaN(Number(v));
    if (isValid(m[key])) return Number(m[key]);

    const traces = m.trace_elements || {};

    switch (key) {
      case 'temperatura':
      case 'temperature':
      case 'temp':
        if (isValid(m.temperatura)) return Number(m.temperatura);
        if (isValid(m.temperature)) return Number(m.temperature);
        if (isValid(m.temperature_c)) return Number(m.temperature_c);
        break;
      case 'salinidad':
      case 'salinity':
      case 'salinity_ppt':
        if (isValid(m.salinity_ppt)) return Number(m.salinity_ppt);
        if (isValid(m.salinity)) return Number(m.salinity);
        break;
      case 'alcalinidad':
      case 'alkalinity_dkh':
      case 'kh':
      case 'dkh':
        if (isValid(m.alkalinity_dkh)) return Number(m.alkalinity_dkh);
        if (isValid(m.kh)) return Number(m.kh);
        break;
      case 'calcio':
      case 'calcium_ppm':
      case 'calcium':
      case 'ca':
        if (isValid(m.calcium_ppm)) return Number(m.calcium_ppm);
        if (isValid(m.calcium)) return Number(m.calcium);
        if (isValid(m.calcio)) return Number(m.calcio);
        break;
      case 'magnesio':
      case 'magnesium_ppm':
      case 'magnesium':
      case 'mg':
        if (isValid(m.magnesium_ppm)) return Number(m.magnesium_ppm);
        if (isValid(m.magnesium)) return Number(m.magnesium);
        if (isValid(m.magnesio)) return Number(m.magnesio);
        break;
      case 'nitratos':
      case 'nitrate_ppm':
      case 'nitrate':
      case 'no3':
        if (isValid(m.nitrate_ppm)) return Number(m.nitrate_ppm);
        if (isValid(m.nitrate)) return Number(m.nitrate);
        if (isValid(m.nitrato)) return Number(m.nitrato);
        break;
      case 'fosfatos':
      case 'phosphate_ppm':
      case 'phosphate':
      case 'po4':
        if (isValid(m.phosphate_ppm)) return Number(m.phosphate_ppm);
        if (isValid(m.phosphate)) return Number(m.phosphate);
        if (isValid(m.fosfato)) return Number(m.fosfato);
        break;
      case 'amoniaco':
      case 'ammonia_ppm':
      case 'ammonia':
      case 'nh3':
        if (isValid(m.ammonia_ppm)) return Number(m.ammonia_ppm);
        if (isValid(m.ammonia)) return Number(m.ammonia);
        break;
      case 'nitritos':
      case 'nitrite_ppm':
      case 'nitrite':
      case 'no2':
        if (isValid(m.nitrite_ppm)) return Number(m.nitrite_ppm);
        if (isValid(m.nitrite)) return Number(m.nitrite);
        break;
      case 'potasio':
      case 'potassium_ppm':
      case 'potassium':
      case 'k':
        if (isValid(m.potassium_ppm)) return Number(m.potassium_ppm);
        if (isValid(m.potassium)) return Number(m.potassium);
        if (isValid(m.potasio)) return Number(m.potasio);
        if (isValid(traces.k)) return Number(traces.k);
        if (isValid(traces.potassium)) return Number(traces.potassium);
        break;
      case 'estroncio':
      case 'strontium_ppm':
      case 'strontium':
      case 'sr':
        if (isValid(m.strontium_ppm)) return Number(m.strontium_ppm);
        if (isValid(m.strontium)) return Number(m.strontium);
        if (isValid(m.estroncio)) return Number(m.estroncio);
        if (isValid(traces.sr)) return Number(traces.sr);
        if (isValid(traces.strontium)) return Number(traces.strontium);
        break;
      case 'yodo':
      case 'iodine_ppm':
      case 'iodine':
      case 'i':
        if (isValid(m.iodine_ppm)) return Number(m.iodine_ppm);
        if (isValid(m.iodine)) return Number(m.iodine);
        if (isValid(m.yodo)) return Number(m.yodo);
        if (isValid(traces.i)) return Number(traces.i);
        if (isValid(traces.iodine)) return Number(traces.iodine);
        break;
      case 'hierro':
      case 'iron_ppm':
      case 'iron':
      case 'fe':
        if (isValid(m.iron_ppm)) return Number(m.iron_ppm);
        if (isValid(m.iron)) return Number(m.iron);
        if (isValid(m.hierro)) return Number(m.hierro);
        if (isValid(traces.fe)) return Number(traces.fe);
        if (isValid(traces.iron)) return Number(traces.iron);
        break;
      case 'gh':
      case 'gh_dgh':
        if (isValid(m.gh_dgh)) return Number(m.gh_dgh);
        if (isValid(m.gh)) return Number(m.gh);
        break;
      case 'co2':
      case 'co2_ppm':
        if (isValid(m.co2_ppm)) return Number(m.co2_ppm);
        if (isValid(m.co2)) return Number(m.co2);
        break;
      default:
        break;
    }
    return null;
  };

  // Filtrar lecturas válidas para el parámetro activo
  const validReadings = useMemo(() => {
    return measurements
      .filter(m => {
        const val = getReadingValue(m, currentParam.key) ?? getReadingValue(m, activeParam);
        return val !== null && !isNaN(val);
      })
      .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
  }, [measurements, currentParam.key, activeParam]);

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
      getReadingValue(r, currentParam.key) ?? getReadingValue(r, activeParam) ?? 0
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
      nitrate_ppm: 15.0,
      ph: 0.5,
      ammonia_ppm: 0.2,
      nitrite_ppm: 0.2,
      gh_dgh: 2.0,
      potassium_ppm: 30.0,
      strontium_ppm: 2.0,
      iodine_ppm: 0.02,
      iron_ppm: 0.01,
      temperature: 3.0,
      temperatura: 3.0
    };
    const maxLimit = maxDailyChange[currentParam.key] || 5.0;
    return Math.max(-maxLimit, Math.min(maxLimit, rawSlope));
  }, [validReadings, currentParam.key, activeParam]);

  // Configurar datasets de Chart.js con la zona segura sombreada y línea punteada de 3 días
  const chartData = useMemo(() => {
    if (validReadings.length === 0) return null;

    // 1. Fechas reales
    const realLabels = validReadings.map(r => {
      const d = new Date(r.timestamp);
      return `${d.getDate()}/${d.getMonth() + 1}`;
    });
    const realValues = validReadings.map(r => getReadingValue(r, currentParam.key) ?? getReadingValue(r, activeParam) ?? 0);

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
  }, [validReadings, currentParam, localSlope, activeParam]);

  const isPhosphate = currentParam.key === 'phosphate_ppm' || activeParam === 'phosphate';
  const isSalinity = currentParam.key === 'salinity_ppt' || currentParam.key === 'salinity' || activeParam === 'salinidad';

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      y: {
        min: isSalinity ? 1.018 : 0, // Bloquea el eje Y apropiadamente
        suggestedMax: currentParam.suggestedMax || (currentParam.safeMax ? currentParam.safeMax * 1.25 : 1.0),
        grid: {
          color: 'rgba(255, 255, 255, 0.05)',
        },
        ticks: { color: '#94a3b8', font: { size: 11, weight: '600' } },
        suggestedMin: isSalinity ? 1.018 : (currentParam.safeMin && currentParam.safeMin > 0 ? currentParam.safeMin * 0.8 : 0)
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
            yMin: currentParam.safeMin !== undefined ? currentParam.safeMin : 0,
            yMax: currentParam.safeMax !== undefined ? currentParam.safeMax : 0.08,
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

      {/* Alertas dinámicas marinas especializadas (KH 24h, Nutrientes en cero, Fotómetro ULR) */}
      {marineAlerts && marineAlerts.length > 0 && (
        <div className="space-y-2.5">
          {marineAlerts.map((alert, idx) => {
            const isCrit = alert.type === 'critical';
            const isWarn = alert.type === 'warning';
            return (
              <div
                key={idx}
                className={`p-4 rounded-2xl border flex items-start gap-3 shadow-lg animate-in fade-in ${
                  isCrit
                    ? 'bg-rose-950/40 border-rose-500/50 text-rose-200 shadow-rose-950/30'
                    : isWarn
                    ? 'bg-amber-950/40 border-amber-500/50 text-amber-200 shadow-amber-950/30'
                    : 'bg-cyan-950/40 border-cyan-500/50 text-cyan-200 shadow-cyan-950/30'
                }`}
              >
                <div className={`p-2 rounded-xl shrink-0 ${
                  isCrit ? 'bg-rose-500/20 text-rose-400 border border-rose-500/40' :
                  isWarn ? 'bg-amber-500/20 text-amber-400 border border-amber-500/40' :
                  'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40'
                }`}>
                  {isCrit ? <ShieldAlert className="w-5 h-5 stroke-[2.2]" /> : <AlertTriangle className="w-5 h-5 stroke-[2.2]" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-extrabold text-sm text-white">{alert.title}</span>
                    <span className={`text-[10px] font-black uppercase px-2 py-0.5 rounded-full ${
                      isCrit ? 'bg-rose-500/20 text-rose-300 border border-rose-500/40' :
                      isWarn ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40' :
                      'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40'
                    }`}>
                      {isCrit ? 'Alerta Crítica' : isWarn ? 'Advertencia' : 'Recomendación'}
                    </span>
                  </div>
                  <p className="text-xs text-slate-300 mt-1 leading-relaxed">{alert.message}</p>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* ---------------- 1. TARJETAS DE ALERTA PREDICTIVA (ARRIBA) ---------------- */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Tarjeta 1: Consumo Diario de Alcalinidad / Buffer */}
        <div className="glass-panel rounded-3xl p-5 border border-cyan-500/40 bg-gradient-to-br from-marine-900/95 via-marine-850 to-marine-900 shadow-neon-cyan relative overflow-hidden flex flex-col justify-between">
          <div className="absolute -right-8 -bottom-8 w-36 h-36 bg-cyan-500/10 rounded-full blur-2xl pointer-events-none" />

          {profileConfig.id === 'fish_only' ? (
            <div className="space-y-3 relative z-10">
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-xl bg-slate-800 text-slate-400 flex items-center justify-center border border-slate-700">
                    <Activity className="w-4 h-4" />
                  </div>
                  <span className="text-xs font-black uppercase tracking-wider text-slate-400">
                    {t('trends.alkConsumption')}
                  </span>
                </div>
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-800 border border-slate-700 text-slate-400 font-bold">
                  No Aplicable
                </span>
              </div>
              <div className="bg-marine-950/80 p-3.5 rounded-2xl border border-marine-800 space-y-1">
                <p className="text-xs sm:text-sm text-slate-300 font-medium leading-relaxed">
                  En acuarios de <strong>Solo Peces (FOWLR)</strong> no hay consumo de carbonatos por corales duros.
                </p>
                <p className="text-xs text-slate-400">
                  La alcalinidad actúa únicamente como colchón buffer para estabilizar el pH entre 8.0 y 8.3. No se requiere dosificación calculada de KH.
                </p>
              </div>
            </div>
          ) : (
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
                        limit: `${profileConfig.ranges?.kh?.min || 7.5} dKH`,
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
          )}

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
                setActiveParam('alcalinidad');
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
                setActiveParam('nitratos');
              }}
              className="text-amber-400 hover:text-amber-300 font-bold flex items-center gap-1"
            >
              {t('trends.viewAccumulation')} <ArrowRight className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>

      {/* ---------------- 2. SELECTOR DE ECOSISTEMA (6 OPCIONES) Y PARÁMETROS DINÁMICOS ---------------- */}
      <div className="space-y-4 mb-6">
        {/* Barra Superior con los 6 Perfiles Canónicos */}
        <div className="flex items-center gap-2 p-1.5 rounded-2xl bg-marine-950/90 border border-marine-800 overflow-x-auto scrollbar-none flex-nowrap sm:flex-wrap">
          {TRENDS_PROFILES.map((tipoItem) => {
            const isSelected = profileConfig.id === tipoItem.id;
            return (
              <button
                key={tipoItem.id}
                type="button"
                onClick={() => handleSelectEcosystem(tipoItem.id)}
                className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs sm:text-sm font-bold transition-all whitespace-nowrap shrink-0 active:scale-95 ${
                  isSelected
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/50 shadow-neon-cyan'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-marine-900/60 border border-transparent'
                }`}
              >
                <span>{tipoItem.label}</span>
              </button>
            );
          })}
        </div>

        {/* Chips de Parámetros Dinámicos filtrados por el perfil activo + Toggle de Elementos Traza */}
        <div className="flex flex-wrap items-center gap-2 sm:gap-2.5">
          {parametrosAMostrar.map((parametro) => {
            const isSelected = activeParam === parametro.id;
            return (
              <button
                key={parametro.id}
                type="button"
                onClick={() => setParametroActivo(parametro.id)}
                className={`px-3 sm:px-4 py-2 rounded-xl border text-xs sm:text-sm font-bold transition-all active:scale-95 flex items-center gap-1.5 ${
                  isSelected
                    ? 'bg-cyan-500/20 border-cyan-400 text-cyan-300 shadow-neon-cyan'
                    : 'bg-marine-900/80 border-marine-800 text-slate-300 hover:bg-marine-850 hover:text-white'
                }`}
              >
                <span>{parametro.nombre}</span>
                {parametro.unidad && (
                  <span className="text-[11px] font-normal opacity-70">{parametro.unidad}</span>
                )}
              </button>
            );
          })}

          {/* Botón especial para alternar Elementos Traza (K, Sr, I, Fe) en perfiles de arrecife */}
          {['sps_reef', 'lps_reef', 'mixed_reef'].includes(profileConfig.id) && (
            <button
              type="button"
              onClick={() => {
                triggerHaptic(15);
                setShowTraceElements(prev => !prev);
              }}
              className={`px-3 sm:px-4 py-2 rounded-xl border text-xs sm:text-sm font-bold transition-all active:scale-95 flex items-center gap-1.5 ${
                showTraceElements
                  ? 'bg-purple-500/25 border-purple-400 text-purple-300 shadow-lg shadow-purple-950/40'
                  : 'bg-purple-950/30 border-purple-500/30 text-purple-300/80 hover:bg-purple-900/40 hover:text-purple-200'
              }`}
            >
              <Sparkles className="w-3.5 h-3.5 text-purple-400" />
              <span>{showTraceElements ? 'Ocultar Traza' : '✨ Elementos Traza (K, Sr, I, Fe)'}</span>
            </button>
          )}
        </div>
      </div>

      {/* ---------------- 3. GRÁFICA INTERACTIVA CON ZONA SEGURA & PROYECCIÓN ---------------- */}
      <div className="glass-panel rounded-3xl p-5 sm:p-7 border border-marine-700/80 space-y-4 shadow-2xl">
        {/* Cabecera Superior (Título y Botones) */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4 pb-4 border-b border-marine-800">
          <div>
            <h2 className="text-2xl font-bold text-white flex items-center flex-wrap gap-y-2">
              {currentParam.name}{' '}
              <span className="ml-3 text-xs bg-emerald-900/50 text-emerald-400 px-2.5 py-1 rounded-lg border border-emerald-800 font-semibold">
                Zona Segura:{' '}
                {currentParam.safeMin !== undefined && currentParam.safeMin !== null
                  ? `${currentParam.safeMin} - ${currentParam.safeMax}`
                  : `< ${currentParam.safeMax}`}{' '}
                {currentParam.unit}
              </span>
            </h2>
            <p className="text-sm text-gray-400 mt-1">Serie histórica con franja verde de rango seguro y proyección punteada a 3 días.</p>
          </div>
          
          {/* Grupo de Acciones */}
          <div className="flex items-center flex-wrap gap-3">
            <button
              type="button"
              onClick={() => {
                triggerHaptic(25);
                if (onOpenQuickLog) onOpenQuickLog(currentParam?.code || currentParam?.key || activeParam, effectiveTank);
              }}
              className="bg-emerald-400 hover:bg-emerald-300 text-slate-900 font-bold py-2 px-4 rounded-lg flex items-center transition-colors active:scale-95"
            >
              <span>📷 Escanear / Registrar</span>
            </button>
            
            {/* NUEVO: Botón de IA integrado en la cabecera */}
            <button 
              type="button"
              onClick={handleAnalizarConIA} /* Usa la función que ya tenías */
              className="bg-cyan-500 hover:bg-cyan-400 text-slate-900 font-bold py-2 px-4 rounded-lg flex items-center shadow-[0_0_15px_rgba(6,182,212,0.4)] transition-all active:scale-95"
            >
              <img src="/robot-fish.jpg" alt="IA" className="w-5 h-5 mr-2 rounded border border-slate-900/20 object-cover" />
              Analizar con IA
            </button>

            <div className="bg-marine-950 px-3.5 py-2 rounded-xl border border-marine-800 text-right hidden lg:block">
              <span className="block text-[10px] font-black uppercase text-slate-400">Pendiente Diaria</span>
              <span className={`text-sm font-black flex items-center justify-end gap-1 ${
                localSlope < 0 ? 'text-amber-400' : 'text-cyan-400'
              }`}>
                {localSlope < 0 ? <TrendingDown className="w-3.5 h-3.5" /> : <TrendingUp className="w-3.5 h-3.5" />}
                {localSlope > 0 ? '+' : ''}{localSlope.toFixed(3)} {currentParam.unit}/d
              </span>
            </div>

            <div className="bg-marine-950 px-3.5 py-2 rounded-xl border border-marine-800 text-right hidden lg:block">
              <span className="block text-[10px] font-black uppercase text-slate-400">Proyección +3 Días</span>
              <span className="text-sm font-black text-white">
                {validReadings.length > 0
                  ? `${Math.max(0, (getReadingValue(validReadings[validReadings.length - 1], currentParam.key) ?? getReadingValue(validReadings[validReadings.length - 1], activeParam) ?? 0) + localSlope * 3).toFixed(2)} ${currentParam.unit}`
                  : '--'}
              </span>
            </div>
          </div>
        </div>

        {/* NUEVO: Panel de IA de Ancho Completo (Se muestra al hacer clic en el botón) */}
        {mostrarDiagnosticoIA && (
          <div className="w-full bg-[#111827] border border-cyan-500/30 rounded-xl p-6 mb-6 shadow-lg shadow-cyan-900/20 animate-fade-in">
            
            {/* Encabezado del Panel IA */}
            <div className="flex items-center justify-between mb-5 border-b border-gray-700/50 pb-4">
              <div className="flex items-center">
                <img 
                  src="/robot-fish.jpg" 
                  alt="AquaPulse AI" 
                  className="w-12 h-12 mr-4 rounded-lg shadow-lg border border-cyan-500/50 object-cover" 
                />
                <div>
                  <h3 className="text-xl font-bold text-cyan-400">Diagnóstico Predictivo AquaPulse</h3>
                  <p className="text-sm text-gray-400">Análisis clínico impulsado por Gemini 2.5 Flash</p>
                </div>
              </div>
              {aiLoading && (
                <div className="flex items-center gap-2 text-xs font-bold text-cyan-400 bg-cyan-950/60 px-3 py-1.5 rounded-full border border-cyan-800">
                  <Activity className="w-4 h-4 animate-spin text-cyan-400" />
                  <span>Analizando química...</span>
                </div>
              )}
            </div>
            
            {/* Grid de 3 columnas para aprovechar el espacio horizontal */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              
              {/* Columna 1: Riesgo */}
              <div className={`p-4 rounded-lg border ${
                aiAnalysis?.nivel_riesgo?.toLowerCase().includes('crítico') || aiAnalysis?.nivel_riesgo?.toLowerCase().includes('alto')
                  ? 'bg-red-900/20 border-red-800/50'
                  : aiAnalysis?.nivel_riesgo?.toLowerCase().includes('moderad')
                  ? 'bg-amber-900/20 border-amber-800/50'
                  : 'bg-emerald-900/20 border-emerald-800/50'
              }`}>
                <span className="text-xs text-gray-400 font-bold uppercase tracking-wider">Nivel de Riesgo</span>
                <p className={`text-xl font-bold mt-1 ${
                  aiAnalysis?.nivel_riesgo?.toLowerCase().includes('crítico') || aiAnalysis?.nivel_riesgo?.toLowerCase().includes('alto')
                    ? 'text-red-400'
                    : aiAnalysis?.nivel_riesgo?.toLowerCase().includes('moderad')
                    ? 'text-amber-400'
                    : 'text-emerald-400'
                }`}>
                  {aiAnalysis?.nivel_riesgo || 'Bajo'}
                </p>
              </div>
              
              {/* Columna 2: Diagnóstico */}
              <div className="bg-slate-800/50 border border-slate-700 p-4 rounded-lg">
                <span className="text-xs text-gray-400 font-bold uppercase tracking-wider">Diagnóstico General</span>
                <p className="text-sm text-gray-300 mt-2">
                  {aiAnalysis?.diagnostico_general || 'El sistema presenta una estabilidad química excelente con parámetros dentro de los rangos óptimos...'}
                </p>
              </div>
              
              {/* Columna 3: Proyección y Acciones */}
              <div className="bg-slate-800/50 border border-slate-700 p-4 rounded-lg">
                <span className="text-xs text-amber-500/80 font-bold uppercase tracking-wider flex items-center">
                  ⚠️ Predicción a 48 Horas
                </span>
                <p className="text-sm text-gray-300 mt-2">
                  {aiAnalysis?.alerta_predictiva_48h || 'Continuará el crecimiento coralino, pero falta registro de temperatura.'}
                </p>
                
                {/* Sugerencia como "Chip" */}
                <div className="mt-3 bg-cyan-900/30 border border-cyan-800 text-cyan-300 text-xs p-2 rounded">
                  <strong>Acción:</strong>{' '}
                  {aiAnalysis?.acciones_correctoras && aiAnalysis.acciones_correctoras.length > 0
                    ? `${aiAnalysis.acciones_correctoras[0].parametro ? aiAnalysis.acciones_correctoras[0].parametro + ': ' : ''}${aiAnalysis.acciones_correctoras[0].producto || ''} ${aiAnalysis.acciones_correctoras[0].cantidad_sugerida ? '(' + aiAnalysis.acciones_correctoras[0].cantidad_sugerida + ')' : ''}`
                    : 'Instalar sensor de monitoreo continuo.'}
                </div>
              </div>
              
            </div>
          </div>
        )}

        {/* Gráfica Original */}
        <div className="h-64 sm:h-80 w-full bg-slate-900/50 rounded-xl p-4 border border-slate-800">
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
    </div>
  );
}
