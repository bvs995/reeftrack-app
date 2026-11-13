# 🚀 Guía de Despliegue en Producción (Cloud) - AquaPulse

Esta guía explica paso a paso cómo desplegar la aplicación en la nube:
- **Backend & Base de Datos**: [Render.com](https://render.com) (FastAPI + PostgreSQL administrado).
- **Frontend PWA**: [Vercel](https://vercel.com) (React 18 + Vite + Service Worker).

---

## 1. Subir el Código a GitHub / GitLab

Asegúrate de inicializar el repositorio y subir tu código (el archivo `.gitignore` ya protege tus claves y bases de datos locales):

```bash
cd /Users/brandonvaladez/.gemini/antigravity/scratch/aquatracker
git init
git add .
git commit -m "feat: preparar AquaPulse para producción con PostgreSQL, Render y Vercel"

# Conecta tu repositorio remoto de GitHub (ejemplo):
git remote add origin https://github.com/TU_USUARIO/aquapulse.git
git branch -M main
git push -u origin main
```

---

## 2. Despliegue del Backend & PostgreSQL en Render

AquaPulse incluye el archivo [`render.yaml`](render.yaml) (Blueprint), el cual provisiona automáticamente el servicio FastAPI y la base de datos PostgreSQL.

### Pasos en Render:
1. Inicia sesión en tu cuenta de [Render Dashboard](https://dashboard.render.com).
2. Haz clic en **Blueprints** en el menú superior o lateral y luego en **New Blueprint Instance**.
3. Conecta y selecciona tu repositorio de GitHub `aquapulse`.
4. Render detectará [`render.yaml`](render.yaml) y mostrará dos recursos a crear:
   - **`aquapulse-postgres`**: Base de datos PostgreSQL 16 administrada.
   - **`aquapulse-backend`**: Servicio Web FastAPI en Python 3.11.
5. Completa las variables de entorno solicitadas:
   - `GEMINI_API_KEY`: Pega tu API Key de Google Gemini (`AQ.Ab8RN6L...`).
   - `ALLOWED_ORIGINS`: Déjalo en `*` temporalmente o pon el dominio que te asigne Vercel (ej: `https://aquapulse.vercel.app`).
6. Haz clic en **Apply**. Render compilará las dependencias desde [`backend/requirements.txt`](backend/requirements.txt), conectará la base de datos PostgreSQL mediante `DATABASE_URL` y arrancará Uvicorn.
7. Una vez finalizado el despliegue, copia la URL pública de tu backend:
   ```
   https://aquapulse-backend.onrender.com
   ```
   *(Verifica que esté activa visitando `https://aquapulse-backend.onrender.com/api/health`)*

---

## 3. Despliegue del Frontend PWA en Vercel

### Pasos en Vercel:
1. Inicia sesión en [Vercel Dashboard](https://vercel.com/dashboard).
2. Haz clic en **Add New...** -> **Project**.
3. Selecciona tu repositorio de GitHub `aquapulse`.
4. En la pantalla de configuración del proyecto:
   - **Framework Preset**: `Vite`
   - **Root Directory**: Haz clic en *Edit* y selecciona la carpeta **`frontend`**.
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
5. En la sección **Environment Variables**, agrega la siguiente variable:
   - **Key**: `VITE_API_URL`
   - **Value**: `https://aquapulse-backend.onrender.com` *(la URL generada por Render en el paso anterior)*
6. Haz clic en **Deploy**.

> **Nota sobre el Enrutamiento PWA**: El archivo [`frontend/vercel.json`](frontend/vercel.json) se encarga automáticamente de redirigir todas las rutas a `/index.html` (SPA routing) y define que `sw.js` (Service Worker) no sea almacenado en caché de larga duración para que los usuarios reciban actualizaciones instantáneas.

---

## 4. Conexión de Variables de Entorno (Resumen)

### Variables en Render (Backend):
| Variable | Descripción | Valor recomendado |
| :--- | :--- | :--- |
| `DATABASE_URL` | Cadena de conexión PostgreSQL | Asignada automáticamente por Render Blueprint |
| `GEMINI_API_KEY` | Clave de Google AI Studio para visión | `AQ.Ab8RN6L...` |
| `VISION_MODEL` | Modelo de visión multimodal | `gemini-3.1-flash-lite` |
| `ALLOWED_ORIGINS` | Orígenes CORS autorizados | `https://tu-app.vercel.app` (o `*`) |
| `DB_POOL_SIZE` | Tamaño del pool de conexiones persistentes | `10` |
| `DB_MAX_OVERFLOW` | Conexiones adicionales en ráfagas | `20` |
| `JWT_SECRET` | Clave criptográfica para tokens de autenticación JWT | Autogenerada por Render o clave secreta de 64 caracteres |

### Variables en Vercel (Frontend):
| Variable | Descripción | Valor recomendado |
| :--- | :--- | :--- |
| `VITE_API_URL` | URL base pública de tu API en Render | `https://aquapulse-backend.onrender.com` |

---

## 5. Checklist de Verificación en Producción

Una vez completados ambos despliegues:

- [ ] Abre en tu navegador `https://aquapulse-backend.onrender.com/api/health` y confirma que devuelva:
  `{"status":"online","database":"connected"}`.
- [ ] Abre tu app en Vercel (`https://tu-app.vercel.app`).
- [ ] Verifica que cargue el historial de mediciones y las gráficas de consumo sin errores de CORS.
- [ ] Prueba el botón **"Escanear Lectura"** desde la cámara de tu móvil para confirmar que Gemini Vision reconozca la foto y complete el formulario.
- [ ] En tu navegador móvil (Safari en iOS o Chrome en Android), pulsa **"Añadir a pantalla de inicio"** para instalar AquaPulse como PWA nativa.
