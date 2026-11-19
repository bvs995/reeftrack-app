/**
 * Perfiles marinos y rangos específicos para AquaPulse.
 * Soporta:
 * 1. fowlr_soft: Solo Peces / Corales Blandos
 * 2. lps_reef: Arrecife LPS (Pólipo Largo)
 * 3. sps_reef: Arrecife SPS (Pólipo Corto)
 */

export const MARINE_PROFILES = {
  fowlr_soft: {
    id: 'fowlr_soft',
    name: 'Solo Peces / Corales Blandos',
    shortName: 'Peces / Blandos',
    description: 'Acuarios marinos solo con peces o corales blandos resistentes (Zoanthus, Sarcophyton, Discosomas).',
    environment: {
      parMin: 50,
      parMax: 100,
      flowProfile: 'low_moderate',
      flowLabel: 'Bajo a moderado'
    },
    targets: {
      salinity: { min: 1.023, max: 1.025, unit: 'SG', step: '0.001', name: 'Salinidad' },
      temperature: { min: 24.0, max: 26.0, unit: '°C', step: '0.1', name: 'Temperatura' },
      ph: { min: 8.0, max: 8.3, unit: 'pH', step: '0.01', name: 'pH' },
      ammonia: { min: 0.0, max: 0.0, safeMax: 0.0, unit: 'ppm', step: '0.01', name: 'Amoníaco (NH3)' },
      nitrite: { min: 0.0, max: 0.0, safeMax: 0.0, unit: 'ppm', step: '0.01', name: 'Nitrito (NO2)' },
      kh: { min: 7.0, max: 10.0, unit: 'dKH', step: '0.1', maxDailyDelta: 1.0, name: 'Alcalinidad (KH)' },
      calcium: { min: 380, max: 420, unit: 'ppm', step: '1', name: 'Calcio (Ca)' },
      magnesium: { min: 1250, max: 1350, unit: 'ppm', step: '1', name: 'Magnesio (Mg)' },
      nitrate: { min: 5.0, max: 20.0, unit: 'ppm', step: '0.1', alertOnZero: false, name: 'Nitrato (NO3)' },
      phosphate: { min: 0.03, max: 0.15, unit: 'ppm', step: '0.001', alertOnZero: false, recommendPhotometer: false, name: 'Fosfato (PO4)' }
    },
    traceElements: {}
  },

  lps_reef: {
    id: 'lps_reef',
    name: 'Arrecife LPS (Pólipo Largo)',
    shortName: 'Arrecife LPS',
    description: 'Corales de pólipo largo (Euphyllias, Acanthastreas, Trachyphyllias, Duncans). Requieren nutrientes detectables y flujo indirecto.',
    environment: {
      parMin: 100,
      parMax: 200,
      flowProfile: 'moderate_indirect',
      flowLabel: 'Moderado e indirecto',
      flowWarning: 'Un chorro directo rasga o desprende el tejido carnoso del coral.'
    },
    targets: {
      salinity: { min: 1.025, max: 1.026, unit: 'SG', step: '0.001', name: 'Salinidad' },
      temperature: { min: 24.5, max: 25.5, unit: '°C', step: '0.1', name: 'Temperatura' },
      ph: { min: 8.1, max: 8.3, unit: 'pH', step: '0.01', name: 'pH' },
      ammonia: { min: 0.0, max: 0.0, safeMax: 0.0, unit: 'ppm', step: '0.01', name: 'Amoníaco (NH3)' },
      nitrite: { min: 0.0, max: 0.0, safeMax: 0.0, unit: 'ppm', step: '0.01', name: 'Nitrito (NO2)' },
      kh: { min: 8.0, max: 9.0, unit: 'dKH', step: '0.1', maxDailyDelta: 0.6, name: 'Alcalinidad (KH)' },
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

  sps_reef: {
    id: 'sps_reef',
    name: 'Arrecife SPS (Pólipo Corto)',
    shortName: 'Arrecife SPS',
    description: 'Corales de pólipo corto (Acroporas, Montiporas, Pocilloporas, Seriatoporas). Exigen altísima estabilidad química, radiación PAR intensa y flujo turbulento.',
    environment: {
      parMin: 250,
      parMax: 450,
      flowProfile: 'high_turbulent',
      flowLabel: 'Muy alto, turbulento y variable'
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
  { id: 'low_moderate', label: 'Bajo a Moderado (Soft / Peces)' },
  { id: 'moderate_indirect', label: 'Moderado e Indirecto (LPS)' },
  { id: 'high_turbulent', label: 'Alto, Turbulento y Variable (SPS)' }
];

export function getMarineProfile(key) {
  if (!key) return MARINE_PROFILES.lps_reef;
  const k = String(key).toLowerCase().trim();
  if (MARINE_PROFILES[k]) return MARINE_PROFILES[k];
  if (k.includes('sps')) return MARINE_PROFILES.sps_reef;
  if (k.includes('pece') || k.includes('soft') || k.includes('fowlr')) return MARINE_PROFILES.fowlr_soft;
  return MARINE_PROFILES.lps_reef;
}
