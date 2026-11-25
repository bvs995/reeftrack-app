// "Reportar un problema": abre el correo del usuario con un reporte prellenado para
// support@aquareef.app (Cloudflare Email Routing lo reenvía al buzón del equipo).
// Solo incluye datos técnicos útiles para reproducir el error; el correo del usuario
// lo pone su propio cliente de correo. Nada se envía si el usuario no pulsa "Enviar".

export const SUPPORT_EMAIL = 'support@aquareef.app';
const APP_VERSION = '1.0.0-beta';
const MAX_ERROR_CHARS = 600; // los enlaces mailto muy largos fallan en algunos clientes

export function buildReportMailto({ error = null, userId = null } = {}) {
  const lines = [
    'Describe qué estabas haciendo y qué pasó:',
    '',
    '',
    '',
    '---- Información técnica (no la borres, nos ayuda a encontrar el error) ----',
    `Versión: ${APP_VERSION}`,
    `Fecha: ${new Date().toISOString()}`,
    `Pantalla: ${typeof window !== 'undefined' ? window.location.pathname : ''}`,
    `Navegador: ${typeof navigator !== 'undefined' ? navigator.userAgent : ''}`,
    `Conexión: ${typeof navigator !== 'undefined' && navigator.onLine === false ? 'sin conexión' : 'en línea'}`,
  ];
  if (typeof window !== 'undefined' && window.matchMedia?.('(display-mode: standalone)').matches) {
    lines.push('Modo: app instalada');
  }
  if (userId) lines.push(`Usuario: #${userId}`);
  if (error) {
    const msg = String(error?.message || error).slice(0, MAX_ERROR_CHARS);
    lines.push(`Error: ${msg}`);
  }

  const subject = error ? 'Error en AquaReef (beta)' : 'Reporte de problema en AquaReef (beta)';
  return `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(lines.join('\n'))}`;
}
