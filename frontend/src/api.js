// En producción (ej: Vercel -> Render), puede definirse VITE_API_URL en las variables de entorno.
// Si no está definida o se usan los rewrites en vercel.json / proxy local, se mantiene '/api'.
const rawUrl = import.meta.env?.VITE_API_URL ? String(import.meta.env.VITE_API_URL).trim() : '';
const API_BASE = rawUrl
  ? (rawUrl.endsWith('/api') ? rawUrl : `${rawUrl.replace(/\/+$/, '')}/api`)
  : '/api';

// ----------------- GESTIÓN DE TOKEN Y AUTENTICACIÓN -----------------

export function getAuthToken() {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('aquapulse_token');
}

export function setAuthToken(token) {
  if (typeof window === 'undefined') return;
  if (token) {
    localStorage.setItem('aquapulse_token', token);
  } else {
    localStorage.removeItem('aquapulse_token');
  }
}

export function getAuthHeaders(customHeaders = {}) {
  const headers = { ...customHeaders };
  const token = getAuthToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

async function authFetch(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  const headers = getAuthHeaders(options.headers || {});
  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('aquapulse:unauthorized'));
    }
  }

  return res;
}

// ----------------- ENDPOINTS DE AUTENTICACIÓN -----------------

export async function loginUser(email, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Error al iniciar sesión');
  }
  const data = await res.json();
  if (data.access_token) {
    setAuthToken(data.access_token);
  }
  return data;
}

export async function registerUser(email, password, fullName = null) {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, full_name: fullName }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Error al registrar la cuenta');
  }
  const data = await res.json();
  if (data.access_token) {
    setAuthToken(data.access_token);
  }
  return data;
}

export async function requestPasswordReset(email) {
  const res = await fetch(`${API_BASE}/auth/forgot-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: email.trim() }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Error al solicitar restablecimiento de contraseña');
  }
  return res.json();
}

export async function confirmPasswordReset(token, newPassword) {
  const res = await fetch(`${API_BASE}/auth/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token: token.trim(), new_password: newPassword }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Error al restablecer la contraseña');
  }
  return res.json();
}

export async function fetchUserProfile() {
  const res = await authFetch('/auth/me');
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Error al obtener perfil de usuario');
  }
  return res.json();
}

export async function updateUserProfile(profileData) {
  const res = await authFetch('/auth/me', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profileData),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Error al actualizar perfil');
  }
  return res.json();
}

// ----------------- ENDPOINTS DIRECTOS SOLICITADOS -----------------

export async function saveMeasurement(data) {
  const res = await authFetch('/measurements', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Error al guardar medición');
  }
  return res.json();
}

export async function fetchMeasurements(limit = 100, order = 'desc') {
  const res = await authFetch(`/measurements?limit=${limit}&order=${order}`);
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Error al obtener historial de mediciones');
  }
  return res.json();
}

export async function fetchPredictions() {
  const res = await authFetch('/predictions');
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Error al obtener cálculo de consumo y predicciones');
  }
  return res.json();
}

export async function scanMeasurement(imageBase64, preferredParameter = null) {
  const res = await authFetch('/scan-measurement', {
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

// ----------------- MÉTODOS DE ACUARIOS Y COMPATIBILIDAD -----------------

export async function fetchTanks() {
  const res = await authFetch('/tanks');
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Error al obtener acuarios');
  }
  return res.json();
}

export async function createTank(data) {
  const res = await authFetch('/tanks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Error al crear acuario');
  }
  return res.json();
}

export async function deleteTank(tankId) {
  const res = await authFetch(`/tanks/${tankId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Error al eliminar acuario');
  }
  return true;
}

export async function fetchTankAnalytics(tankId) {
  const res = await authFetch(`/tanks/${tankId}/analytics`);
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Error al obtener análisis y predicciones');
  }
  return res.json();
}

export async function fetchTankParameters(tankId) {
  const res = await authFetch(`/tanks/${tankId}/parameters`);
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Error al obtener parámetros del acuario');
  }
  return res.json();
}

export async function fetchChartData(tankId, parameterCode = null) {
  const url = parameterCode
    ? `/tanks/${tankId}/chart-data?parameter_code=${parameterCode}`
    : `/tanks/${tankId}/chart-data`;
  const res = await authFetch(url);
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Error al obtener datos históricos para gráficas');
  }
  return res.json();
}

export async function recordMeasurement(tankId, data) {
  // Asegurar inclusión explícita del ID del acuario
  const payload = { ...data };
  if (tankId && !payload.tank_id) {
    payload.tank_id = tankId;
  }

  // Mapear código de parámetro numérico si viene en formato individual
  if (payload.parameter_code && payload.value !== undefined) {
    const codeMap = {
      dkh: 'alkalinity_dkh',
      alkalinity: 'alkalinity_dkh',
      alkalinity_dkh: 'alkalinity_dkh',
      ca: 'calcium_ppm',
      calcium: 'calcium_ppm',
      calcium_ppm: 'calcium_ppm',
      mg: 'magnesium_ppm',
      magnesium: 'magnesium_ppm',
      magnesium_ppm: 'magnesium_ppm',
      no3: 'nitrate_ppm',
      nitrate: 'nitrate_ppm',
      nitrate_ppm: 'nitrate_ppm',
      po4: 'phosphate_ppm',
      phosphate: 'phosphate_ppm',
      phosphate_ppm: 'phosphate_ppm',
      salinity: 'salinity_ppt',
      salinity_ppt: 'salinity_ppt'
    };
    const field = codeMap[payload.parameter_code] || payload.parameter_code;
    payload[field] = parseFloat(payload.value);
  }

  // Soporta tanto la ruta /api/tanks/:id/measurements como /api/measurements
  const targetUrl = tankId ? `/tanks/${tankId}/measurements` : '/measurements';
  const res = await authFetch(targetUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Error al registrar medición');
  }
  return res.json();
}

export async function recordBatchMeasurements(tankId, batchData) {
  const res = await authFetch(`/tanks/${tankId}/measurements/batch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(batchData),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Error al registrar lote de mediciones');
  }
  return res.json();
}

export async function deleteMeasurement(measurementId) {
  const res = await authFetch(`/measurements/${measurementId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Error al eliminar medición');
  }
  return true;
}

export async function fetchWaterChanges(tankId) {
  const res = await authFetch(`/tanks/${tankId}/water-changes`);
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Error al obtener cambios de agua');
  }
  return res.json();
}

export async function recordWaterChange(tankId, data) {
  const res = await authFetch(`/tanks/${tankId}/water-changes`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Error al registrar cambio de agua');
  }
  return res.json();
}

// ----------------- PANEL DE CONTROL DE ADMINISTRADOR -----------------

export async function fetchAdminUsers() {
  const res = await authFetch('/admin/users');
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Error al obtener usuarios para administración');
  }
  return res.json();
}

export async function updateAdminUser(userId, data) {
  const res = await authFetch(`/admin/users/${userId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Error al actualizar usuario');
  }
  return res.json();
}

export async function deleteAdminUser(userId) {
  const res = await authFetch(`/admin/users/${userId}`, {
    method: 'DELETE',
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Error al eliminar usuario');
  }
  return res.json();
}
