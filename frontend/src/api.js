// En producción (ej: Vercel -> Render), puede definirse VITE_API_URL en las variables de entorno.
// Si no está definida o se usan los rewrites en vercel.json / proxy local, se mantiene '/api'.
const rawUrl = import.meta.env?.VITE_API_URL ? String(import.meta.env.VITE_API_URL).trim() : '';
const API_BASE = rawUrl
  ? (rawUrl.endsWith('/api') ? rawUrl : `${rawUrl.replace(/\/+$/, '')}/api`)
  : '/api';

// ----------------- ENDPOINTS DIRECTOS SOLICITADOS -----------------

export async function saveMeasurement(data) {
  const res = await fetch(`${API_BASE}/measurements`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Error al guardar medición');
  return res.json();
}

export async function fetchMeasurements(limit = 100, order = 'desc') {
  const res = await fetch(`${API_BASE}/measurements?limit=${limit}&order=${order}`);
  if (!res.ok) throw new Error('Error al obtener historial de mediciones');
  return res.json();
}

export async function fetchPredictions() {
  const res = await fetch(`${API_BASE}/predictions`);
  if (!res.ok) throw new Error('Error al obtener cálculo de consumo y predicciones');
  return res.json();
}

export async function scanMeasurement(imageBase64, preferredParameter = null) {
  const res = await fetch(`${API_BASE}/scan-measurement`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      image_base64: imageBase64,
      preferred_parameter: preferredParameter,
      demo_fallback: true
    }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Error al analizar la fotografía del test');
  }
  return res.json();
}

// ----------------- MÉTODOS DE COMPATIBILIDAD -----------------

export async function fetchTanks() {
  const res = await fetch(`${API_BASE}/tanks`);
  if (!res.ok) throw new Error('Error al obtener acuarios');
  return res.json();
}

export async function createTank(data) {
  const res = await fetch(`${API_BASE}/tanks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Error al crear acuario');
  return res.json();
}

export async function deleteTank(tankId) {
  const res = await fetch(`${API_BASE}/tanks/${tankId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Error al eliminar acuario');
  return true;
}

export async function fetchTankAnalytics(tankId) {
  const res = await fetch(`${API_BASE}/tanks/${tankId}/analytics`);
  if (!res.ok) throw new Error('Error al obtener análisis y predicciones');
  return res.json();
}

export async function fetchTankParameters(tankId) {
  const res = await fetch(`${API_BASE}/tanks/${tankId}/parameters`);
  if (!res.ok) throw new Error('Error al obtener parámetros del acuario');
  return res.json();
}

export async function fetchChartData(tankId, parameterCode = null) {
  const url = parameterCode
    ? `${API_BASE}/tanks/${tankId}/chart-data?parameter_code=${parameterCode}`
    : `${API_BASE}/tanks/${tankId}/chart-data`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Error al obtener datos históricos para gráficas');
  return res.json();
}

export async function recordMeasurement(tankId, data) {
  const res = await fetch(`${API_BASE}/tanks/${tankId}/measurements`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Error al registrar medición');
  return res.json();
}

export async function recordBatchMeasurements(tankId, batchData) {
  const res = await fetch(`${API_BASE}/tanks/${tankId}/measurements/batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(batchData),
  });
  if (!res.ok) throw new Error('Error al registrar lote de mediciones');
  return res.json();
}

export async function deleteMeasurement(measurementId) {
  const res = await fetch(`${API_BASE}/measurements/${measurementId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error('Error al eliminar medición');
  return true;
}

export async function fetchWaterChanges(tankId) {
  const res = await fetch(`${API_BASE}/tanks/${tankId}/water-changes`);
  if (!res.ok) throw new Error('Error al obtener cambios de agua');
  return res.json();
}

export async function recordWaterChange(tankId, data) {
  const res = await fetch(`${API_BASE}/tanks/${tankId}/water-changes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error('Error al registrar cambio de agua');
  return res.json();
}
