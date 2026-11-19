/**
 * Perfiles marinos y rangos específicos para AquaPulse.
 * Soporta exactamente 5 perfiles:
 * 1. fish_only: Solo Peces / FOWLR
 * 2. soft_reef: Corales Blandos
 * 3. lps_reef: Arrecife LPS (Pólipo Largo)
 * 4. mixed_reef: Arrecife Mixto (Blandos + LPS + SPS)
 * 5. sps_reef: Arrecife SPS (Pólipo Corto)
 */

export const MARINE_PROFILES = {
  // 1. SOLO PECES / FOWLR
  fish_only: {
    id: 'fish_only',
    name: 'Solo Peces / FOWLR',
    shortName: 'Peces / FOWLR',
    description: 'Acuarios marinos solo con peces o roca viva (FOWLR). Sin demanda de calcificación coralina.',
    environment: {
      parMin: null,
      parMax: null,
      flowProfile: 'low_moderate',
      flowLabel: 'Bajo a moderado'
    },
    visible_fields: {
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
      trace_elements: false,
      test_methods: false,
      lighting_par: false,
      flow_profile: false,
      dosing_method: false
    },
    enabled_rules: {
      kh_delta_24h: false,
      zero_nutrient_floor: false,
      test_resolution_po4: false,
      automated_dosing_suggestion: false,
      flow_tissue_warning: false
    },
    targets: {
      salinity: { min: 1.020, max: 1.025, unit: 'SG', step: '0.001', name: 'Salinidad' },
      temperature: { min: 24.0, max: 26.0, unit: '°C', step: '0.1', name: 'Temperatura' },
      ph: { min: 8.0, max: 8.3, unit: 'pH', step: '0.01', name: 'pH' },
      ammonia: { min: 0.0, max: 0.0, safeMax: 0.0, unit: 'ppm', step: '0.01', name: 'Amoníaco (NH3)' },
      nitrite: { min: 0.0, max: 0.0, safeMax: 0.0, unit: 'ppm', step: '0.01', name: 'Nitrito (NO2)' },
      nitrate: { min: 0.0, max: 30.0, unit: 'ppm', step: '0.5', alertOnZero: false, name: 'Nitrato (NO3)' },
      kh: { min: 7.0, max: 11.0, unit: 'dKH', step: '0.1', name: 'Alcalinidad (KH)' },
      phosphate: { min: 0.0, max: 0.25, unit: 'ppm', step: '0.01', alertOnZero: false, name: 'Fosfato (PO4)' }
    },
    traceElements: {}
  },

  // 2. CORALES BLANDOS
  soft_reef: {
    id: 'soft_reef',
    name: 'Corales Blandos',
    shortName: 'Blandos (Soft)',
    description: 'Corales blandos resistentes (Zoanthus, Sarcophyton, Discosomas). Toleran nutrientes y no requieren dosificación de trazas.',
    environment: {
      parMin: 50,
      parMax: 120,
      flowProfile: 'low_moderate',
      flowLabel: 'Bajo a moderado'
    },
    visible_fields: {
      salinity: true,
      temperature: true,
      ph: true,
      ammonia: true,
      nitrite: true,
      nitrate: true,
      kh: true,
      phosphate: true,
      calcium: true,
      magnesium: true,
      trace_elements: false,
      test_methods: false,
      lighting_par: true,
      flow_profile: true,
      dosing_method: true
    },
    enabled_rules: {
      kh_delta_24h: true,
      zero_nutrient_floor: true,
      test_resolution_po4: false,
      automated_dosing_suggestion: false,
      flow_tissue_warning: false
    },
    targets: {
      salinity: { min: 1.023, max: 1.025, unit: 'SG', step: '0.001', name: 'Salinidad' },
      temperature: { min: 24.0, max: 26.0, unit: '°C', step: '0.1', name: 'Temperatura' },
      ph: { min: 8.0, max: 8.3, unit: 'pH', step: '0.01', name: 'pH' },
      ammonia: { min: 0.0, max: 0.0, safeMax: 0.0, unit: 'ppm', step: '0.01', name: 'Amoníaco (NH3)' },
      nitrite: { min: 0.0, max: 0.0, safeMax: 0.0, unit: 'ppm', step: '0.01', name: 'Nitrito (NO2)' },
      kh: { min: 7.5, max: 9.5, unit: 'dKH', step: '0.1', maxDailyDelta: 1.0, name: 'Alcalinidad (KH)' },
      calcium: { min: 380, max: 420, unit: 'ppm', step: '1', name: 'Calcio (Ca)' },
      magnesium: { min: 1250, max: 1350, unit: 'ppm', step: '1', name: 'Magnesio (Mg)' },
      nitrate: { min: 5.0, max: 15.0, unit: 'ppm', step: '0.1', alertOnZero: true, name: 'Nitrato (NO3)' },
      phosphate: { min: 0.05, max: 0.15, unit: 'ppm', step: '0.001', alertOnZero: true, name: 'Fosfato (PO4)' }
    },
    traceElements: {}
  },

  // 3. ARRECIFE LPS (Pólipo Largo)
  lps_reef: {
    id: 'lps_reef',
    name: 'Arrecife LPS (Pólipo Largo)',
    shortName: 'Arrecife LPS',
    description: 'Corales duros de pólipo largo (Euphyllias, Torch, Acanthastreas, Duncans). Requieren nutrientes detectables y flujo indirecto.',
    environment: {
      parMin: 100,
      parMax: 200,
      flowProfile: 'moderate_indirect',
      flowLabel: 'Moderado e indirecto',
      flowWarning: 'Un chorro directo fuerte rasga o desprende el tejido carnoso del coral LPS.'
    },
    visible_fields: {
      salinity: true,
      temperature: true,
      ph: true,
      ammonia: true,
      nitrite: true,
      nitrate: true,
      kh: true,
      phosphate: true,
      calcium: true,
      magnesium: true,
      trace_elements: true,
      test_methods: true,
      lighting_par: true,
      flow_profile: true,
      dosing_method: true
    },
    enabled_rules: {
      kh_delta_24h: true,
      zero_nutrient_floor: true,
      test_resolution_po4: true,
      automated_dosing_suggestion: true,
      flow_tissue_warning: true
    },
    targets: {
      salinity: { min: 1.025, max: 1.026, unit: 'SG', step: '0.001', name: 'Salinidad' },
      temperature: { min: 24.5, max: 25.5, unit: '°C', step: '0.1', name: 'Temperatura' },
      ph: { min: 8.1, max: 8.3, unit: 'pH', step: '0.01', name: 'pH' },
      ammonia: { min: 0.0, max: 0.0, safeMax: 0.0, unit: 'ppm', step: '0.01', name: 'Amoníaco (NH3)' },
      nitrite: { min: 0.0, max: 0.0, safeMax: 0.0, unit: 'ppm', step: '0.01', name: 'Nitrito (NO2)' },
      kh: { min: 8.0, max: 9.0, unit: 'dKH', step: '0.1', maxDailyDelta: 0.6, warnDailyDelta: 0.6, name: 'Alcalinidad (KH)' },
      calcium: { min: 400, max: 440, unit: 'ppm', step: '1', name: 'Calcio (Ca)' },
      magnesium: { min: 1300, max: 1350, unit: 'ppm', step: '1', name: 'Magnesio (Mg)' },
      nitrate: { min: 5.0, max: 10.0, unit: 'ppm', step: '0.1', alertOnZero: true, name: 'Nitrato (NO3)' },
      phosphate: { min: 0.03, max: 0.08, ideal: 0.05, unit: 'ppm', step: '0.001', alertOnZero: true, recommendPhotometer: true, name: 'Fosfato (PO4)' }
    },
    traceElements: {
      k: { min: 380, max: 410, unit: 'ppm', step: '1', name: 'Potasio (K)' },
      sr: { min: 8.0, max: 10.0, unit: 'ppm', step: '0.1', name: 'Estroncio (Sr)' },
      i: { min: 0.03, max: 0.06, unit: 'ppm', step: '0.01', name: 'Yodo (I)' },
      fe: { min: 0.001, max: 0.005, unit: 'ppm', step: '0.001', name: 'Hierro (Fe)' }
    }
  },

  // 4. ARRECIFE MIXTO (Blandos + LPS + SPS)
  mixed_reef: {
    id: 'mixed_reef',
    name: 'Arrecife Mixto (Blandos + LPS + SPS)',
    shortName: 'Arrecife Mixto',
    description: 'Composición balanceada de corales blandos, LPS y SPS. Demanda equilibrio químico para alimentar LPS sin saturar ni blanquear los SPS.',
    environment: {
      parMin: 150,
      parMax: 300,
      flowProfile: 'moderate_indirect',
      flowLabel: 'Medio-alto variable por zonas'
    },
    visible_fields: {
      salinity: true,
      temperature: true,
      ph: true,
      ammonia: true,
      nitrite: true,
      nitrate: true,
      kh: true,
      phosphate: true,
      calcium: true,
      magnesium: true,
      trace_elements: true,
      test_methods: true,
      lighting_par: true,
      flow_profile: true,
      dosing_method: true
    },
    enabled_rules: {
      kh_delta_24h: true,
      zero_nutrient_floor: true,
      test_resolution_po4: true,
      automated_dosing_suggestion: true,
      flow_tissue_warning: true
    },
    targets: {
      salinity: { min: 1.025, max: 1.026, unit: 'SG', step: '0.001', name: 'Salinidad' },
      temperature: { min: 24.5, max: 25.5, unit: '°C', step: '0.1', name: 'Temperatura' },
      ph: { min: 8.1, max: 8.3, unit: 'pH', step: '0.01', name: 'pH' },
      ammonia: { min: 0.0, max: 0.0, safeMax: 0.0, unit: 'ppm', step: '0.01', name: 'Amoníaco (NH3)' },
      nitrite: { min: 0.0, max: 0.0, safeMax: 0.0, unit: 'ppm', step: '0.01', name: 'Nitrito (NO2)' },
      kh: { min: 8.0, max: 8.5, unit: 'dKH', step: '0.1', warnDailyDelta: 0.4, criticalDailyDelta: 0.5, name: 'Alcalinidad (KH)' },
      calcium: { min: 420, max: 440, unit: 'ppm', step: '1', name: 'Calcio (Ca)' },
      magnesium: { min: 1300, max: 1350, unit: 'ppm', step: '1', name: 'Magnesio (Mg)' },
      nitrate: { min: 3.0, max: 8.0, unit: 'ppm', step: '0.1', alertOnZero: true, name: 'Nitrato (NO3)' },
      phosphate: { min: 0.03, max: 0.06, unit: 'ppm', step: '0.001', alertOnZero: true, recommendPhotometer: true, name: 'Fosfato (PO4)' }
    },
    traceElements: {
      k: { min: 390, max: 410, unit: 'ppm', step: '1', name: 'Potasio (K)' },
      sr: { min: 8.0, max: 10.0, unit: 'ppm', step: '0.1', name: 'Estroncio (Sr)' },
      i: { min: 0.03, max: 0.06, unit: 'ppm', step: '0.01', name: 'Yodo (I)' },
      fe: { min: 0.001, max: 0.005, unit: 'ppm', step: '0.001', name: 'Hierro (Fe)' }
    }
  },

  // 5. ARRECIFE SPS (Pólipo Corto)
  sps_reef: {
    id: 'sps_reef',
    name: 'Arrecife SPS (Pólipo Corto)',
    shortName: 'Arrecife SPS',
    description: 'Corales duros de pólipo corto (Acroporas, Montiporas, Pocilloporas, Seriatoporas). Exigen altísima estabilidad química, radiación PAR intensa (250-450+) y flujo turbulento.',
    environment: {
      parMin: 250,
      parMax: 450,
      flowProfile: 'high_turbulent',
      flowLabel: 'Muy alto, turbulento y variable'
    },
    visible_fields: {
      salinity: true,
      temperature: true,
      ph: true,
      ammonia: true,
      nitrite: true,
      nitrate: true,
      kh: true,
      phosphate: true,
      calcium: true,
      magnesium: true,
      trace_elements: true,
      test_methods: true,
      lighting_par: true,
      flow_profile: true,
      dosing_method: true
    },
    enabled_rules: {
      kh_delta_24h: true,
      zero_nutrient_floor: true,
      test_resolution_po4: true,
      automated_dosing_suggestion: true,
      flow_tissue_warning: false
    },
    targets: {
      salinity: { min: 1.025, max: 1.026, unit: 'SG', step: '0.001', name: 'Salinidad' },
      temperature: { min: 24.5, max: 25.5, max24hDelta: 0.5, unit: '°C', step: '0.1', name: 'Temperatura' },
      ph: { min: 8.2, max: 8.3, unit: 'pH', step: '0.01', name: 'pH' },
      ammonia: { min: 0.0, max: 0.0, safeMax: 0.0, unit: 'ppm', step: '0.01', name: 'Amoníaco (NH3)' },
      nitrite: { min: 0.0, max: 0.0, safeMax: 0.0, unit: 'ppm', step: '0.01', name: 'Nitrito (NO2)' },
      kh: { min: 7.5, max: 8.5, unit: 'dKH', step: '0.1', warnDailyDelta: 0.3, criticalDailyDelta: 0.5, name: 'Alcalinidad (KH)' },
      calcium: { min: 420, max: 450, unit: 'ppm', step: '1', name: 'Calcio (Ca)' },
      magnesium: { min: 1300, max: 1400, unit: 'ppm', step: '1', name: 'Magnesio (Mg)' },
      nitrate: { min: 1.0, max: 5.0, unit: 'ppm', step: '0.1', alertOnZero: true, name: 'Nitrato (NO3)' },
      phosphate: { min: 0.01, max: 0.04, unit: 'ppm', step: '0.001', alertOnZero: true, recommendPhotometer: true, name: 'Fosfato (PO4)' }
    },
    traceElements: {
      k: { min: 390, max: 410, unit: 'ppm', step: '1', name: 'Potasio (K)' },
      sr: { min: 8.0, max: 10.0, unit: 'ppm', step: '0.1', name: 'Estroncio (Sr)' },
      i: { min: 0.03, max: 0.06, unit: 'ppm', step: '0.01', name: 'Yodo (I)' },
      fe: { min: 0.001, max: 0.005, unit: 'ppm', step: '0.001', name: 'Hierro (Fe)' }
    }
  }
};

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

export function getMarineProfile(key) {
  if (!key) return MARINE_PROFILES.lps_reef;
  const k = String(key).toLowerCase().trim();
  if (MARINE_PROFILES[k]) return MARINE_PROFILES[k];

  // Mapeo defensivo de sinónimos
  if (k.includes('fish') || k.includes('fowlr') || k.includes('solo_peces') || k.includes('marine_fish')) {
    return MARINE_PROFILES.fish_only;
  }
  if (k.includes('soft') || k.includes('blando')) {
    return MARINE_PROFILES.soft_reef;
  }
  if (k.includes('mixed') || k.includes('mixto')) {
    return MARINE_PROFILES.mixed_reef;
  }
  if (k.includes('sps') || k.includes('acropora')) {
    return MARINE_PROFILES.sps_reef;
  }
  if (k.includes('lps')) {
    return MARINE_PROFILES.lps_reef;
  }

  return MARINE_PROFILES.lps_reef;
}
