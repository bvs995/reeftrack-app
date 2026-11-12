# 🌊 AquaPulse | Progressive Web App (PWA) para Acuarios & Reef

**AquaPulse** es una Progressive Web App de alta precisión diseñada tanto para acuarios marinos de arrecife (**Reef SPS/LPS**) como para acuarios de agua dulce (**Aquascaping Plantado High-Tech / Comunitario**).

Su objetivo fundamental es eliminar la fricción en el registro diario de mediciones y proporcionar **analítica predictiva proactiva**:
- Cálculo automático de **tasas de consumo diario** ($\Delta \text{unidades}/\text{día}$).
- **Proyección de fechas límite** antes de que un buffer (como el KH o Calcio) caiga por debajo del umbral de seguridad ($7.5 - 9.0\text{ dKH}$).
- **Predicción de Cambios de Agua** basados en acumulación de nitratos y fosfatos, con simulador interactivo de dilución y cálculo de sal sintética requerida.
- **Web Notifications API** con recordatorios locales en el navegador a la hora programada por el usuario.
- **Alertas Bioquímicas Expertas** (estabilización de alcalinidad, ratios Redfield N:P, prevención de RTN/STN).

---

## 🛠️ Stack Tecnológico

- **Frontend**:
  - React 18 con Vite (Fast HMR & build optimizado para PWA).
  - Tailwind CSS con diseño náutico/neón (`slate-900`, `cyan-400`, `emerald-400`).
  - Lucide Icons para iconografía moderna.
  - Chart.js & `react-chartjs-2` con franjas de rango seguro sombreadas y líneas punteadas proyectadas a +3 días.
  - Service Worker (`sw.js`) y `manifest.json` para instalación como app nativa.
- **Backend**:
  - Python con **FastAPI** (asíncrono, fuertemente tipado con Pydantic v2).
  - Motor de regresión lineal simple (`backend/analytics.py`) para deducción de tendencias.
- **Base de Datos**:
  - **SQLAlchemy 2.0 ORM** compatible con:
    - **PostgreSQL** para entornos de producción (Render, Supabase, Neon, AWS RDS) con connection pooling y reconexión automática (`pool_pre_ping`).
    - **SQLite** persistente local (`aquatracker.db`) como fallback automático para desarrollo sin dependencias externas.

---

## 🚀 Despliegue en Producción

### Arquitectura de Producción
```
┌─────────────────────────────────┐           ┌─────────────────────────────────┐
│         Vercel (Frontend)       │           │          Render (Backend)       │
│  - React PWA (Vite Build)       │ ────────> │  - FastAPI Python Service       │
│  - Service Worker Caching       │  REST API │  - Predictive Analytics Engine  │
│  - Web Notifications API        │           │  - Connection Pool (10/20)      │
└─────────────────────────────────┘           └───────────────┬─────────────────┘
                                                              │ SQLAlchemy
                                                              ▼
                                              ┌─────────────────────────────────┐
                                              │      Render PostgreSQL DB       │
                                              │  - Managed Instance (Postgres16)│
                                              │  - Auto migrations & Seeds      │
                                              └─────────────────────────────────┘
```

---

### 1. Despliegue del Backend en Render

AquaPulse incluye un archivo [`render.yaml`](render.yaml) (Render Blueprint) que automatiza la creación del servicio web y de la base de datos PostgreSQL:

1. Ve a tu panel en [Render Dashboard](https://dashboard.render.com).
2. Haz clic en **Blueprints** -> **New Blueprint Instance**.
3. Conecta tu repositorio de GitHub/GitLab.
4. Render leerá [`render.yaml`](render.yaml) y provisionará automáticamente:
   - La base de datos administrada **`aquapulse-postgres`** (PostgreSQL 16).
   - El servicio web **`aquapulse-backend`** con FastAPI, vinculando automáticamente `DATABASE_URL` y ejecutando migraciones iniciales.
5. Copia la URL pública generada (ej: `https://aquapulse-backend.onrender.com`).

#### Variables de Entorno del Backend en Render:
| Variable | Descripción | Valor por defecto |
| :--- | :--- | :--- |
| `DATABASE_URL` | URL de conexión asignada por Render | Asignada por Render Blueprint |
| `ALLOWED_ORIGINS` | Dominios permitidos para CORS (tu app en Vercel) | `https://tu-app.vercel.app` o `*` |
| `PORT` | Puerto asignado por Render | `8000` |
| `DB_POOL_SIZE` | Tamaño del pool de conexiones persistentes | `10` |
| `DB_MAX_OVERFLOW` | Conexiones adicionales permitidas en ráfagas | `20` |

---

### 2. Despliegue del Frontend en Vercel

1. Ve a [Vercel Dashboard](https://vercel.com/dashboard) y haz clic en **Add New Project**.
2. Conecta el repositorio de AquaPulse.
3. Configuración del proyecto:
   - **Framework Preset**: `Vite`
   - **Root Directory**: `frontend` *(o raíz si usas el `vercel.json` principal)*
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
4. En **Environment Variables**, añade:
   ```env
   VITE_API_URL=https://aquapulse-backend.onrender.com
   ```
5. Haz clic en **Deploy**. El archivo [`frontend/vercel.json`](frontend/vercel.json) asegurará el enrutamiento SPA y la política de caché óptima para Service Worker y PWA.

---

### 3. Prueba Local con Docker Compose (PostgreSQL Real)

Puedes levantar la pila idéntica a producción (PostgreSQL 16 + FastAPI Backend) en un solo comando:

```bash
docker compose up --build
```

El servicio estará disponible en:
- API & Docs: `http://localhost:8000/docs`
- Healthcheck: `http://localhost:8000/api/health`
- Base de datos Postgres en `localhost:5432` con persistencia en volumen `pgdata`.

---

## 💻 Desarrollo Local (SQLite Zero-Config)

Para desarrollo diario sin requerir Docker ni PostgreSQL:

```bash
cd /Users/brandonvaladez/.gemini/antigravity/scratch/aquatracker
./run.sh
```

Abre en tu navegador:
👉 **[http://localhost:8000](http://localhost:8000)**

Si deseas trabajar con Hot-Reload independiente:
```bash
# Terminal 1 - Backend FastAPI con recarga en vivo:
cd backend
PYTHONPATH=.. ./venv/bin/python3 -m uvicorn backend.main:app --reload --port 8000

# Terminal 2 - Frontend Vite:
cd frontend
npm run dev
# Abre http://localhost:5173
```
