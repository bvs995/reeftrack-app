/**
 * Perfiles bioquímicos y configuración de ecosistemas para AquaPulse.
 * Soporta exactamente 6 opciones maestras:
 * 1. freshwater: Agua Dulce
 * 2. planted: Plantado
 * 3. fish_only: Solo Peces / Marino FOWLR
 * 4. mixed_reef: Arrecife Mixto (Blandos + LPS + SPS)
 * 5. lps_reef: Arrecife LPS (Corales de Pólipo Largo)
 * 6. sps_reef: Arrecife SPS (Corales de Pólipo Corto)
 */

export const TANK_PROFILES = {
  // 1. AGUA DULCE ESTÁNDAR
  freshwater: {
    id: 'freshwater',
    name: 'Agua Dulce Estándar',
    shortName: 'Agua Dulce',
    badge: 'Agua Dulce',
    isMarine: false,
    description: 'Acuarios comunitarios de agua dulce o peces de agua fría/tropicales sin requerimientos intensivos de CO2 ni calcificación.',
    environment: {
      parMin: null,
      parMax: null,
      flowProfile: 'low_moderate',
      flowLabel: 'Moderado'
    },
    visibleFields: {
      salinity: false,
      temperature: true,
      ph: true,
      ammonia: true,
      nitrite: true,
      nitrate: true,
      kh: false,
      phosphate: false,
      calcium: false,
      magnesium: false,
      gh_dgh: true,
      potassium: false,
      iron: false,
      co2: false,
      trace_elements: false,
      test_methods: false,
      lighting_par: false,
      flow_profile: false,
      dosing_method: false
    },
    rules: {
      kh_delta_24h: false,
      zero_nutrient_floor: false,
      test_resolution_po4: false,
      automated_dosing_suggestion: false,
      flow_tissue_warning: false
    },
    ranges: {
      temperature: { min: 23.0, max: 27.0, target: 25.0, unit: '°C', step: '0.1', name: 'Temperatura' },
      ph: { min: 6.5, max: 7.8, target: 7.2, unit: '', step: '0.01', name: 'pH' },
      ammonia: { min: 0.0, max: 0.02, target: 0.0, safeMax: 0.02, unit: 'ppm', step: '0.01', name: 'Amoníaco (NH3)' },
      nitrite: { min: 0.0, max: 0.05, target: 0.0, safeMax: 0.05, unit: 'ppm', step: '0.01', name: 'Nitrito (NO2)' },
      nitrate: { min: 0.0, max: 30.0, target: 10.0, unit: 'ppm', step: '0.5', alertOnZero: false, name: 'Nitrato (NO3)' },
      gh_dgh: { min: 4.0, max: 10.0, target: 6.0, unit: 'dGH', step: '0.5', name: 'Dureza General (GH)' }
    },
    traceElements: {}
  },

  // 2. AGUA DULCE PLANTADO
  planted: {
    id: 'planted',
    name: 'Agua Dulce Plantado',
    shortName: 'Plantado',
    badge: 'Plantado',
    isMarine: false,
    description: 'Acuarios plantados de alta densidad y aquascaping (Iwagumi, Holandés). Demanda fertilización de macro/micronutrientes y CO2.',
    environment: {
      parMin: 30,
      parMax: 100,
      flowProfile: 'low_moderate',
      flowLabel: 'Moderado uniforme'
    },
    visibleFields: {
      salinity: false,
      temperature: true,
      ph: true,
      ammonia: true,
      nitrite: true,
      nitrate: true,
      kh: true,
      phosphate: true,
      calcium: false,
      magnesium: false,
      gh_dgh: true,
      potassium: true,
      iron: true,
      co2: true,
      trace_elements: false,
      test_methods: false,
      lighting_par: true,
      flow_profile: false,
      dosing_method: true
    },
    rules: {
      kh_delta_24h: false,
      zero_nutrient_floor: false,
      test_resolution_po4: false,
      automated_dosing_suggestion: false,
      flow_tissue_warning: false
    },
    ranges: {
      temperature: { min: 22.0, max: 26.5, target: 24.5, unit: '°C', step: '0.1', name: 'Temperatura' },
      ph: { min: 6.0, max: 7.2, target: 6.6, unit: '', step: '0.01', name: 'pH' },
      ammonia: { min: 0.0, max: 0.02, target: 0.0, safeMax: 0.02, unit: 'ppm', step: '0.01', name: 'Amoníaco (NH3)' },
      nitrite: { min: 0.0, max: 0.05, target: 0.0, safeMax: 0.05, unit: 'ppm', step: '0.01', name: 'Nitrito (NO2)' },
      nitrate: { min: 5.0, max: 25.0, target: 15.0, unit: 'ppm', step: '0.5', alertOnZero: false, name: 'Nitrato (NO3)' },
      phosphate: { min: 0.5, max: 2.5, target: 1.2, unit: 'ppm', step: '0.01', alertOnZero: false, name: 'Fosfato (PO4)' },
      kh: { min: 3.0, max: 8.0, target: 5.0, unit: 'dKH', step: '0.1', name: 'Alcalinidad (KH)' },
      gh_dgh: { min: 4.0, max: 9.0, target: 6.0, unit: 'dGH', step: '0.5', name: 'Dureza General (GH)' },
      potassium: { min: 10.0, max: 25.0, target: 15.0, unit: 'ppm', step: '0.5', name: 'Potasio (K)' },
      iron: { min: 0.05, max: 0.5, target: 0.1, unit: 'ppm', step: '0.01', name: 'Hierro (Fe)' },
      co2: { min: 15.0, max: 35.0, target: 25.0, unit: 'ppm', step: '1.0', name: 'CO2 Disuelto' }
    },
    traceElements: {}
  },

  // 3. SOLO PECES / FOWLR MARINO
  fish_only: {
    id: 'fish_only',
    name: 'Solo Peces (Marino FOWLR)',
    shortName: 'Solo Peces',
    badge: 'Solo Peces',
    isMarine: true,
    description: 'Acuarios marinos con peces o roca viva (FOWLR). Sin demanda de calcificación ni iluminación coralina.',
    environment: {
      parMin: null,
      parMax: null,
      flowProfile: 'low_moderate',
      flowLabel: 'Bajo a moderado'
    },
    visibleFields: {
      salinity: true,
      temperature: true,
      ph: true,
      ammonia: true,
      nitrite: true,
      nitrate: true,
      kh: true,
      phosphate: true,
      calcium: false,
      magnesium: false,
      gh_dgh: false,
      potassium: false,
      iron: false,
      co2: false,
      trace_elements: false,
      test_methods: false,
      lighting_par: false,
      flow_profile: false,
      dosing_method: false
    },
    rules: {
      kh_delta_24h: false,
      zero_nutrient_floor: false,
      test_resolution_po4: false,
      automated_dosing_suggestion: false,
      flow_tissue_warning: false
    },
    ranges: {
      salinity: { min: 1.020, max: 1.025, target: 1.023, unit: 'SG', step: '0.001', name: 'Salinidad' },
      temperature: { min: 24.0, max: 26.0, target: 25.0, unit: '°C', step: '0.1', name: 'Temperatura' },
      ph: { min: 8.0, max: 8.3, target: 8.15, unit: '', step: '0.01', name: 'pH' },
      ammonia: { min: 0.0, max: 0.0, target: 0.0, safeMax: 0.0, unit: 'ppm', step: '0.01', name: 'Amoníaco (NH3)' },
      nitrite: { min: 0.0, max: 0.0, target: 0.0, safeMax: 0.0, unit: 'ppm', step: '0.01', name: 'Nitrito (NO2)' },
      nitrate: { min: 0.0, max: 30.0, target: 15.0, unit: 'ppm', step: '0.5', alertOnZero: false, name: 'Nitrato (NO3)' },
      kh: { min: 7.0, max: 11.0, target: 8.5, unit: 'dKH', step: '0.1', name: 'Alcalinidad (KH) (Opcional)' },
      phosphate: { min: 0.0, max: 0.25, target: 0.10, unit: 'ppm', step: '0.01', alertOnZero: false, name: 'Fosfato (PO4) (Opcional)' }
    },
    traceElements: {}
  },

  // 4. ARRECIFE MIXTO (Blandos + LPS + SPS)
  mixed_reef: {
    id: 'mixed_reef',
    name: 'Arrecife Mixto (Blandos + LPS + SPS)',
    shortName: 'Arrecife Mixto',
    badge: 'Arrecife Mixto',
    isMarine: true,
    description: 'Composición balanceada de corales blandos, LPS y SPS. Demanda equilibrio químico para alimentar LPS sin desestabilizar SPS.',
    environment: {
      parMin: 150,
      parMax: 300,
      flowProfile: 'moderate_indirect',
      flowLabel: 'Medio-alto variable por zonas'
    },
    visibleFields: {
      salinity: true,
      temperature: true,
      ph: true,
      ammonia: true,
      nitrite: true,
      kh: true,
      calcium: true,
      magnesium: true,
      nitrate: true,
      phosphate: true,
      gh_dgh: false,
      potassium: false,
      iron: false,
      co2: false,
      trace_elements: true,
      test_methods: true,
      lighting_par: true,
      flow_profile: true,
      dosing_method: true
    },
    rules: {
      kh_delta_24h: true,
      warn_daily_delta_kh: 0.4,
      critical_daily_delta_kh: 0.5,
      zero_nutrient_floor: true,
      test_resolution_po4: true,
      automated_dosing_suggestion: true,
      flow_tissue_warning: false
    },
    ranges: {
      salinity: { min: 1.025, max: 1.026, target: 1.0255, unit: 'SG', step: '0.001', name: 'Salinidad' },
      temperature: { min: 24.5, max: 25.5, target: 25.0, unit: '°C', step: '0.1', name: 'Temperatura' },
      ph: { min: 8.1, max: 8.3, target: 8.2, unit: '', step: '0.01', name: 'pH' },
      ammonia: { min: 0.0, max: 0.0, target: 0.0, safeMax: 0.0, unit: 'ppm', step: '0.01', name: 'Amoníaco (NH3)' },
      nitrite: { min: 0.0, max: 0.0, target: 0.0, safeMax: 0.0, unit: 'ppm', step: '0.01', name: 'Nitrito (NO2)' },
      kh: { min: 8.0, max: 8.5, target: 8.25, unit: 'dKH', step: '0.1', warnDailyDelta: 0.4, criticalDailyDelta: 0.5, name: 'Alcalinidad (KH)' },
      calcium: { min: 420, max: 440, target: 430, unit: 'ppm', step: '1', name: 'Calcio (Ca)' },
      magnesium: { min: 1300, max: 1350, target: 1325, unit: 'ppm', step: '1', name: 'Magnesio (Mg)' },
      nitrate: { min: 3.0, max: 8.0, target: 5.0, unit: 'ppm', step: '0.1', alertOnZero: true, name: 'Nitrato (NO3)' },
      phosphate: { min: 0.03, max: 0.06, target: 0.045, ideal: 0.045, unit: 'ppm', step: '0.001', alertOnZero: true, recommendPhotometer: true, name: 'Fosfato (PO4)' }
    },
    traceElements: {
      k: { min: 390, max: 410, target: 400, unit: 'ppm', step: '1', name: 'Potasio (K)' },
      sr: { min: 8.0, max: 10.0, target: 9.0, unit: 'ppm', step: '0.1', name: 'Estroncio (Sr)' },
      i: { min: 0.03, max: 0.06, target: 0.05, unit: 'ppm', step: '0.01', name: 'Yodo (I)' },
      fe: { min: 0.001, max: 0.005, target: 0.003, unit: 'ppm', step: '0.001', name: 'Hierro (Fe)' }
    }
  },

  // 5. ARRECIFE LPS (Corales de Pólipo Largo)
  lps_reef: {
    id: 'lps_reef',
    name: 'Arrecife LPS (Corales de Pólipo Largo)',
    shortName: 'Arrecife LPS',
    badge: 'Arrecife LPS',
    isMarine: true,
    description: 'Corales duros de pólipo carnoso (Euphyllia, Torch, Acans, Duncans, Goniopora). Requieren nutrientes estables y flujo indirecto.',
    environment: {
      parMin: 100,
      parMax: 200,
      flowProfile: 'moderate_indirect',
      flowLabel: 'Moderado e indirecto',
      flowWarning: 'El flujo laminar directo rasga el tejido carnoso de los corales LPS.'
    },
    visibleFields: {
      salinity: true,
      temperature: true,
      ph: true,
      ammonia: true,
      nitrite: true,
      kh: true,
      calcium: true,
      magnesium: true,
      nitrate: true,
      phosphate: true,
      gh_dgh: false,
      potassium: false,
      iron: false,
      co2: false,
      trace_elements: true,
      test_methods: true,
      lighting_par: true,
      flow_profile: true,
      dosing_method: true
    },
    rules: {
      kh_delta_24h: true,
      warn_daily_delta_kh: 0.6,
      critical_daily_delta_kh: 0.8,
      zero_nutrient_floor: true,
      test_resolution_po4: true,
      automated_dosing_suggestion: true,
      flow_tissue_warning: true
    },
    ranges: {
      salinity: { min: 1.025, max: 1.026, target: 1.0255, unit: 'SG', step: '0.001', name: 'Salinidad' },
      temperature: { min: 24.5, max: 25.5, target: 25.0, unit: '°C', step: '0.1', name: 'Temperatura' },
      ph: { min: 8.1, max: 8.3, target: 8.2, unit: '', step: '0.01', name: 'pH' },
      ammonia: { min: 0.0, max: 0.0, target: 0.0, safeMax: 0.0, unit: 'ppm', step: '0.01', name: 'Amoníaco (NH3)' },
      nitrite: { min: 0.0, max: 0.0, target: 0.0, safeMax: 0.0, unit: 'ppm', step: '0.01', name: 'Nitrito (NO2)' },
      kh: { min: 8.0, max: 9.0, target: 8.5, unit: 'dKH', step: '0.1', warnDailyDelta: 0.6, name: 'Alcalinidad (KH)' },
      calcium: { min: 400, max: 440, target: 420, unit: 'ppm', step: '1', name: 'Calcio (Ca)' },
      magnesium: { min: 1300, max: 1350, target: 1325, unit: 'ppm', step: '1', name: 'Magnesio (Mg)' },
      nitrate: { min: 5.0, max: 10.0, target: 7.5, unit: 'ppm', step: '0.1', alertOnZero: true, name: 'Nitrato (NO3)' },
      phosphate: { min: 0.03, max: 0.08, target: 0.05, ideal: 0.05, unit: 'ppm', step: '0.001', alertOnZero: true, recommendPhotometer: true, name: 'Fosfato (PO4)' }
    },
    traceElements: {
      k: { min: 380, max: 410, target: 395, unit: 'ppm', step: '1', name: 'Potasio (K)' },
      sr: { min: 8.0, max: 10.0, target: 9.0, unit: 'ppm', step: '0.1', name: 'Estroncio (Sr)' },
      i: { min: 0.03, max: 0.06, target: 0.045, unit: 'ppm', step: '0.01', name: 'Yodo (I)' },
      fe: { min: 0.001, max: 0.005, target: 0.003, unit: 'ppm', step: '0.001', name: 'Hierro (Fe)' }
    }
  },

  // 6. ARRECIFE SPS (Corales de Pólipo Corto)
  sps_reef: {
    id: 'sps_reef',
    name: 'Arrecife SPS (Corales de Pólipo Corto)',
    shortName: 'Arrecife SPS',
    badge: 'Arrecife SPS',
    isMarine: true,
    description: 'Corales duros SPS de máxima exigencia (Acropora, Montipora, Millepora, Seriatopora). Exigen estabilidad ultra-estricta, PAR intenso y flujo turbulento.',
    environment: {
      parMin: 250,
      parMax: 450,
      flowProfile: 'high_turbulent',
      flowLabel: 'Muy alto, turbulento y variable'
    },
    visibleFields: {
      salinity: true,
      temperature: true,
      ph: true,
      ammonia: true,
      nitrite: true,
      kh: true,
      calcium: true,
      magnesium: true,
      nitrate: true,
      phosphate: true,
      gh_dgh: false,
      potassium: false,
      iron: false,
      co2: false,
      trace_elements: true,
      test_methods: true,
      lighting_par: true,
      flow_profile: true,
      dosing_method: true
    },
    rules: {
      kh_delta_24h: true,
      warn_daily_delta_kh: 0.3,
      critical_daily_delta_kh: 0.5,
      zero_nutrient_floor: true,
      test_resolution_po4: true,
      recommend_photometer_icp: true,
      split_daily_dosing: true,
      flow_tissue_warning: false
    },
    ranges: {
      salinity: { min: 1.025, max: 1.026, target: 1.0255, unit: 'SG', step: '0.001', name: 'Salinidad' },
      temperature: { min: 24.5, max: 25.5, target: 25.0, max24hDelta: 0.5, unit: '°C', step: '0.1', name: 'Temperatura' },
      ph: { min: 8.2, max: 8.3, target: 8.25, unit: '', step: '0.01', name: 'pH' },
      ammonia: { min: 0.0, max: 0.0, target: 0.0, safeMax: 0.0, unit: 'ppm', step: '0.01', name: 'Amoníaco (NH3)' },
      nitrite: { min: 0.0, max: 0.0, target: 0.0, safeMax: 0.0, unit: 'ppm', step: '0.01', name: 'Nitrito (NO2)' },
      kh: { min: 7.5, max: 8.5, target: 8.0, unit: 'dKH', step: '0.1', warnDailyDelta: 0.3, criticalDailyDelta: 0.5, name: 'Alcalinidad (KH)' },
      calcium: { min: 420, max: 450, target: 435, unit: 'ppm', step: '1', name: 'Calcio (Ca)' },
      magnesium: { min: 1300, max: 1400, target: 1350, unit: 'ppm', step: '1', name: 'Magnesio (Mg)' },
      nitrate: { min: 1.0, max: 5.0, target: 3.0, unit: 'ppm', step: '0.1', alertOnZero: true, name: 'Nitrato (NO3)' },
      phosphate: { min: 0.01, max: 0.04, target: 0.025, ideal: 0.025, unit: 'ppm', step: '0.001', alertOnZero: true, recommendPhotometer: true, name: 'Fosfato (PO4)' }
    },
    traceElements: {
      k: { min: 390, max: 410, target: 400, unit: 'ppm', step: '1', name: 'Potasio (K)' },
      sr: { min: 8.0, max: 10.0, target: 9.0, unit: 'ppm', step: '0.1', name: 'Estroncio (Sr)' },
      i: { min: 0.03, max: 0.06, target: 0.05, unit: 'ppm', step: '0.01', name: 'Yodo (I)' },
      fe: { min: 0.001, max: 0.005, target: 0.003, unit: 'ppm', step: '0.001', name: 'Hierro (Fe)' }
    }
  }
};

// Aliases para retrocompatibilidad
TANK_PROFILES.soft_reef = TANK_PROFILES.lps_reef;
export const MARINE_PROFILES = TANK_PROFILES;

export const DOSING_METHODS = [
  { id: 'water_changes', label: 'Cambios de Agua' },
  { id: 'manual_dosing', label: 'Dosificación Manual' },
  { id: 'peristaltic_balling', label: 'Balling / Bombas Peristálticas' },
  { id: 'kalkwasser', label: 'Kalkwasser (Agua de Cal)' },
  { id: 'calcium_reactor', label: 'Reactor de Calcio (CaRx)' }
];

export const FLOW_PROFILES = [
  { id: 'low_moderate', label: 'Bajo a Moderado' },
  { id: 'moderate_indirect', label: 'Moderado e Indirecto (LPS)' },
  { id: 'high_turbulent', label: 'Alto, Turbulento y Variable (SPS)' }
];

/**
 * Normaliza cualquier clave histórica o sinónimo a una de las 6 claves maestras:
 * freshwater, planted, fish_only, mixed_reef, lps_reef, sps_reef
 */
export function normalizeProfileKey(raw) {
  if (!raw) return 'lps_reef';
  const k = String(raw).toLowerCase().trim();

  // Agua Dulce
  if (k === 'freshwater' || k === 'dulce' || k === 'freshwater_community' || k === 'dulce_peces' || k.includes('dulce')) {
    return 'freshwater';
  }
  // Plantado
  if (k === 'planted' || k === 'plantado' || k === 'freshwater_planted' || k.includes('plant')) {
    return 'planted';
  }
  // Solo Peces
  if (
    k === 'fish_only' ||
    k === 'marine_fish' ||
    k === 'peces_marinos' ||
    k === 'peces' ||
    k === 'fowlr' ||
    k === 'fowlr_soft' ||
    k.includes('pece')
  ) {
    return 'fish_only';
  }
  // Arrecife Mixto
  if (k === 'mixed_reef' || k === 'mixed' || k === 'mixto' || k.includes('mixt')) {
    return 'mixed_reef';
  }
  // Arrecife SPS
  if (k === 'sps_reef' || k === 'sps' || k.includes('sps') || k.includes('acropora')) {
    return 'sps_reef';
  }
  // Arrecife LPS (y fallback de arrecife genérico / blandos)
  if (k === 'lps_reef' || k === 'lps' || k === 'arrecife' || k === 'reef' || k === 'soft_reef' || k === 'soft' || k.includes('arrecif') || k.includes('reef')) {
    return 'lps_reef';
  }

  return 'lps_reef';
}

/**
 * Obtiene la configuración maestra unificada para cualquier acuario o clave.
 * Acepta string de tipo/perfil O el objeto completo del acuario (tank).
 */
export function getProfileConfig(tankOrKey) {
  let rawKey = tankOrKey;
  if (tankOrKey && typeof tankOrKey === 'object') {
    rawKey =
      tankOrKey.reef_profile ||
      tankOrKey.tank_type ||
      tankOrKey.tipo ||
      tankOrKey.tipoAgua ||
      tankOrKey.type;
  }

  const key = normalizeProfileKey(rawKey);
  const profile = TANK_PROFILES[key] || TANK_PROFILES.lps_reef;

  // Propiedades complementarias de retrocompatibilidad con componentes antiguos
  return {
    ...profile,
    targets: profile.ranges,
    visible_fields: profile.visibleFields,
    enabled_rules: profile.rules
  };
}

/**
 * Alias de retrocompatibilidad para getProfileConfig
 */
export const getMarineProfile = getProfileConfig;
