"""
AquaPulse - Commercial Multi-User API Gateway (P2.17 Modularized)
"""
import os
import uuid
import logging
import urllib.parse
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from backend.database import get_db, init_db, check_db_connection
from backend.seed import seed_database_if_empty
from backend.marine_profiles import MARINE_PROFILES

# Routers modulares (P2.17)
from backend.routers import (
    auth_router,
    admin_router,
    tanks_router,
    measurements_router,
    ai_router,
    maintenance_router,
    push_router,
    legal_router,
)

# Re-exportaciones para compatibilidad con suites de tests existentes
from backend.rate_limits import (
    get_client_ip,
    auth_attempts,
    scan_quota_manager,
    UserScanQuotaManager,
    check_auth_rate_limit,
)
from backend.routers.tanks import update_aquarium

logger = logging.getLogger("aquapulse.main")

# Asegurar creación inicial de tablas al cargar el módulo
try:
    init_db()
except Exception as _e:
    logger.debug(f"Aviso en init_db de carga de módulo: {_e}")

is_production = os.getenv("ENVIRONMENT", "").strip().lower() == "production"

# Inicialización de la aplicación FastAPI (/docs deshabilitado en producción)
app = FastAPI(
    title="AquaPulse Commercial Multi-User API",
    description="Backend SaaS multi-usuario de alta precisión para acuarios con autenticación JWT y aislamiento de datos.",
    version="3.0.0",
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json",
)

# Configuración estricta de CORS con lista blanca
raw_origins = os.environ.get("ALLOWED_ORIGINS", "").strip()
if raw_origins and raw_origins != "*":
    origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
    allow_creds = True
else:
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:8000",
    ]
    allow_creds = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware de seguridad HTTP y trazabilidad con Request-ID (UUID4)
@app.middleware("http")
async def security_and_request_id_middleware(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    response = await call_next(request)

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"

    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https:; img-src 'self' data: https: blob:; "
        "font-src 'self' data: https:; connect-src 'self' https: wss:; frame-ancestors 'none';"
    )

    if is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response


# Manejador global de excepciones 500 genéricas
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=getattr(exc, "headers", None),
        )
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.exception(f"Unhandled server exception [request_id={req_id}]: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Error interno del servidor. Por favor contacte a soporte indicando el identificador del incidente.",
            "request_id": req_id,
        },
        headers={"X-Request-ID": req_id},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Convierte errores de validación de Pydantic en HTTP 400 Bad Request con detalle claro."""
    errors = exc.errors()
    first_error = errors[0] if errors else {}
    msg = first_error.get("msg", "Error de validación en los datos enviados.")
    if msg.startswith("Value error, "):
        msg = msg[len("Value error, "):]
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": msg},
    )


@app.on_event("startup")
def startup_event():
    try:
        init_db()
    except Exception as e:
        logger.error(f"Error durante init_db en startup: {e}")

    try:
        db = next(get_db())
        try:
            seed_database_if_empty(db)
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Aviso durante seed_database_if_empty en startup: {e}")


# ==============================================================================
# 🩺 HEALTH CHECK PÚBLICO MÍNIMO (P2.13)
# ==============================================================================

@app.get("/api/health", summary="Health check público mínimo del servicio y base de datos (P2.13)")
def health_check(db: Session = Depends(get_db)):
    """
    Endpoint público mínimo: solo realiza ping a la base de datos y retorna {'status': 'ok'}.
    Las métricas de IA (gasto, descarte) están protegidas en /api/admin/ai-audit-stats.
    """
    db_ok = check_db_connection()
    if not db_ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "error", "database": "disconnected"},
        )
    return {"status": "ok", "database": "connected"}


# ==============================================================================
# 🌊 CATÁLOGO DE PERFILES MARINOS Y DULCES (FASE 5)
# ==============================================================================

@app.get(
    "/api/marine-profiles",
    summary="Listar todos los perfiles de acuarios (marinos y de agua dulce)"
)
def get_marine_profiles_endpoint():
    """Retorna el catálogo completo de biotipos y perfiles de referencia oficiales de AquaPulse."""
    return {
        "status": "success",
        "profiles": list(MARINE_PROFILES.values()),
    }


# ==============================================================================
# 📦 INCLUSIÓN DE ROUTERS MODULARES (P2.17)
# ==============================================================================

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(tanks_router)
app.include_router(measurements_router)
app.include_router(ai_router)
app.include_router(maintenance_router)
app.include_router(push_router)
app.include_router(legal_router)


# ==============================================================================
# 🌐 SERVICIO DE LA PWA (SPA FALLBACK Y PROTECCIÓN TRAVERSAL P0.3)
# ==============================================================================

DIST_DIR = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))).resolve()

if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        decoded_path = urllib.parse.unquote(full_path).lstrip("/")
        index_file = DIST_DIR / "index.html"

        if decoded_path:
            try:
                target_file = (DIST_DIR / decoded_path).resolve()
                if target_file.is_relative_to(DIST_DIR) and target_file.is_file():
                    return FileResponse(str(target_file))
            except Exception:
                pass

        if index_file.exists():
            return FileResponse(str(index_file))
        return {"status": "AquaPulse API is active"}
