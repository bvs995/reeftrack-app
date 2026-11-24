import os
import uuid
import secrets
import hashlib
import time
import threading
import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Query, Body, status, BackgroundTasks, Header, Request, Response, Cookie
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

logger = logging.getLogger("aquapulse.main")

from backend.database import get_db, init_db, check_db_connection
from backend.models import (
    User,
    Tank,
    Measurement,
    UserRegister,
    UserLogin,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    PasswordResetResponse,
    UserUpdate,
    UserResponse,
    TokenResponse,
    TankCreate,
    AquariumCreate,
    TankResponse,
    MeasurementCreate,
    MeasurementResponse,
    PredictionResponse,
    AdminUserUpdate,
    AdminUserListItem,
    check_password_complexity,
    PASSWORD_REQUIREMENTS_ERROR,
    DosisRecomendada,
    AnalisisAcuarioSchema,
    AnalisisAcuarioResponse,
    AquariumDataRequest,
    AquariumAnalysisResponse,
    PredictiveAnalysisJsonResponse,
    MedicionAcuario,
    Acuario,
    Aquarium,
    MaintenanceTask,
    MaintenanceLog,
    WaterChange,
    DiagnosticFeedback,
    DiagnosticFeedbackCreate,
    DiagnosticFeedbackResponse,
    MaintenanceTaskCreate,
    MaintenanceTaskUpdate,
    MaintenanceTaskResponse,
    MaintenanceCompleteRequest,
    WaterChangeCreate,
    WaterChangeResponse,
    PushSubscription,
    PushSubscriptionCreate,
    PushUnsubscribeRequest,
    PushPreferencesUpdate,
    PushSubscriptionResponse,
    PasswordResetToken,
    DiagnosticAudit,
    DiagnosticAuditResponse,
    DiagnosticAuditStatsResponse
)
from backend.push_service import (
    get_vapid_public_key,
    get_cron_secret,
    send_push_to_user,
    check_and_notify_measurement_alert,
    process_daily_maintenance_reminders
)
from backend.maintenance_service import (
    seed_default_maintenance_tasks,
    calculate_task_status,
    task_to_response_dict
)
from backend.services.ai_service import (
    analizar_parametros_acuario,
    analizar_parametros_estructurado,
    analizar_acuario_estructurado,
    obtener_tendencia_ultimas_48h
)
from backend.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_password_reset_token,
    verify_password_reset_token,
    send_password_reset_email,
    create_email_verification_token,
    verify_email_verification_token,
    send_email_verification,
    get_current_user,
    get_optional_current_user,
    get_current_admin_user
)
from backend.analytics import calculate_predictions
from backend.seed import seed_database_if_empty
from backend.vision import (
    ScanMeasurementRequest,
    ScanMeasurementResponse,
    analyze_test_image
)

# Determinación estricta de entorno
is_production = os.getenv("ENVIRONMENT", "").strip().lower() == "production"

# Rate limiting in-memory con ventana deslizante para endpoints de autenticación (/api/auth/*)
auth_attempts: Dict[str, List[float]] = defaultdict(list)
auth_lock = threading.Lock()
AUTH_RATE_LIMIT_MAX = 5
AUTH_RATE_LIMIT_WINDOW_SECONDS = 60.0

def check_auth_rate_limit(request: Request):
    """Aplica rate limit estricto por IP a los endpoints de autenticación (máx 5 peticiones/minuto)."""
    ip = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()

    now = time.time()
    with auth_lock:
        timestamps = auth_attempts[ip]
        valid_timestamps = [ts for ts in timestamps if now - ts < AUTH_RATE_LIMIT_WINDOW_SECONDS]
        if len(valid_timestamps) >= AUTH_RATE_LIMIT_MAX:
            auth_attempts[ip] = valid_timestamps
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiadas solicitudes de autenticación. Por favor espera un minuto antes de reintentar."
            )
        valid_timestamps.append(now)
        auth_attempts[ip] = valid_timestamps

# Control de cuota diaria y rate limit por usuario para escaneos IA con Gemini
class UserScanQuotaManager:
    """
    Control de cuotas y rate limiting por usuario para escaneos de tests con IA.
    Protege los costos del modelo de visión (Google Gemini) limitando:
    - Plan Free: Máximo 5 escaneos por día natural (UTC), burst de 5 peticiones/minuto.
    - Plan Premium / Admin: Máximo 100 escaneos por día natural (UTC), burst de 15 peticiones/minuto.
    """
    def __init__(self):
        self._lock = threading.Lock()
        # Estructura: user_id -> {"date": "YYYY-MM-DD", "count": int, "timestamps": [float, ...]}
        self._usage: Dict[int, Dict[str, Any]] = defaultdict(dict)

    def _get_daily_limit(self, subscription_tier: str, is_admin: bool) -> int:
        if is_admin:
            return int(os.environ.get("SCAN_DAILY_LIMIT_ADMIN", "500"))
        if subscription_tier == "premium":
            return int(os.environ.get("SCAN_DAILY_LIMIT_PREMIUM", "100"))
        return int(os.environ.get("SCAN_DAILY_LIMIT_FREE", "5"))

    def _get_burst_limit(self, subscription_tier: str, is_admin: bool) -> int:
        if is_admin or subscription_tier == "premium":
            return 15
        return 5

    def get_quota_info(self, user_id: int, subscription_tier: str, is_admin: bool) -> Dict[str, Any]:
        now_utc = datetime.now(timezone.utc)
        today_str = now_utc.strftime("%Y-%m-%d")
        daily_limit = self._get_daily_limit(subscription_tier, is_admin)

        tomorrow_utc = datetime.combine(now_utc.date() + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        reset_seconds = max(1, int((tomorrow_utc - now_utc).total_seconds()))

        with self._lock:
            record = self._usage.get(user_id, {})
            if record.get("date") != today_str:
                used = 0
            else:
                used = record.get("count", 0)

        remaining = max(0, daily_limit - used)
        return {
            "tier": "admin" if is_admin else subscription_tier,
            "daily_quota": daily_limit,
            "used_today": used,
            "remaining_today": remaining,
            "reset_seconds": reset_seconds
        }

    def check_and_consume(self, user_id: int, subscription_tier: str, is_admin: bool) -> Dict[str, Any]:
        now_utc = datetime.now(timezone.utc)
        now_ts = now_utc.timestamp()
        today_str = now_utc.strftime("%Y-%m-%d")
        daily_limit = self._get_daily_limit(subscription_tier, is_admin)
        burst_limit = self._get_burst_limit(subscription_tier, is_admin)

        tomorrow_utc = datetime.combine(now_utc.date() + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        reset_seconds = max(1, int((tomorrow_utc - now_utc).total_seconds()))

        with self._lock:
            record = self._usage[user_id]
            if record.get("date") != today_str:
                record["date"] = today_str
                record["count"] = 0
                record["timestamps"] = []

            # 1. Verificar cuota diaria primero
            current_count = record.get("count", 0)
            if current_count >= daily_limit:
                tier_msg = "plan gratuito" if subscription_tier == "free" and not is_admin else "plan actual"
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Has alcanzado tu límite diario de {daily_limit} escaneos IA en el {tier_msg}. "
                        f"Tu cuota se reiniciará a las 00:00 UTC ({reset_seconds // 3600}h {(reset_seconds % 3600) // 60}m restantes), "
                        f"o puedes actualizar a Premium para ampliar tu límite."
                    ),
                    headers={
                        "X-RateLimit-Limit": str(daily_limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(reset_seconds)
                    }
                )

            # 2. Verificar burst limit (últimos 60s)
            timestamps = [ts for ts in record.get("timestamps", []) if now_ts - ts < 60.0]
            if len(timestamps) >= burst_limit:
                record["timestamps"] = timestamps
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Demasiadas peticiones de escaneo en poco tiempo. Por favor espera un minuto antes de reintentar.",
                    headers={
                        "X-RateLimit-Limit": str(daily_limit),
                        "X-RateLimit-Remaining": str(max(0, daily_limit - record["count"])),
                        "X-RateLimit-Reset": str(reset_seconds),
                        "Retry-After": "60"
                    }
                )

            # 3. Consumir escaneo
            current_count += 1
            record["count"] = current_count
            timestamps.append(now_ts)
            record["timestamps"] = timestamps

            remaining = max(0, daily_limit - current_count)
            return {
                "tier": "admin" if is_admin else subscription_tier,
                "daily_quota": daily_limit,
                "used_today": current_count,
                "remaining_today": remaining,
                "reset_seconds": reset_seconds
            }

    def reset_for_tests(self):
        with self._lock:
            self._usage.clear()

scan_quota_manager = UserScanQuotaManager()

# Inicialización de la aplicación FastAPI (/docs deshabilitado en producción)
app = FastAPI(
    title="AquaPulse Commercial Multi-User API",
    description="Backend SaaS multi-usuario de alta precisión para acuarios con autenticación JWT y aislamiento de datos.",
    version="3.0.0",
    docs_url=None if is_production else "/docs",
    redoc_url=None if is_production else "/redoc",
    openapi_url=None if is_production else "/openapi.json"
)

# Configuración estricta de CORS con lista blanca (nunca wildcard '*' con credenciales)
raw_origins = os.environ.get("ALLOWED_ORIGINS", "").strip()
if raw_origins and raw_origins != "*":
    origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
    allow_creds = True
else:
    # Lista blanca segura para desarrollo local y PWA
    origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:8000"
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

    if is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline' https:; "
            "style-src 'self' 'unsafe-inline' https:; img-src 'self' data: https: blob:; "
            "font-src 'self' data: https:; connect-src 'self' https: wss:; frame-ancestors 'none';"
        )

    return response

# Manejador global de excepciones 500 genéricas (oculta stacktrace técnico, loguea con request_id)
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=getattr(exc, "headers", None)
        )
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.exception(f"Unhandled server exception [request_id={req_id}]: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Error interno del servidor. Por favor contacte a soporte indicando el identificador del incidente.",
            "request_id": req_id
        },
        headers={"X-Request-ID": req_id}
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
        content={"detail": msg}
    )

@app.on_event("startup")
def startup_event():
    # Inicializa las tablas de SQLAlchemy y auto-migraciones de forma defensiva
    try:
        init_db()
    except Exception as e:
        logger.error(f"Error durante init_db en startup: {e}")

    # Sembrado inicial de datos seguro y no bloqueante
    try:
        db = next(get_db())
        try:
            seed_database_if_empty(db)
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Aviso durante seed_database_if_empty en startup: {e}")

@app.get("/api/health", summary="Monitor operativo de salud del sistema, base de datos y IA")
def health_check(db: Session = Depends(get_db)):
    db_ok = check_db_connection()
    from backend.services.ai_service import get_ai_audit_statistics
    ai_stats = get_ai_audit_statistics(db)

    # El servicio está 'degraded' si la tasa de descarte es anómala o si se excedió el presupuesto
    is_degraded = ai_stats.get("discard_rate_alert") or ai_stats.get("budget_status") == "exceeded"
    status_str = "online" if db_ok and not is_degraded else ("degraded" if db_ok else "offline")

    health_data = {
        "status": status_str,
        "database": "connected" if db_ok else "disconnected",
        "service": "AquaPulse Multi-User Predictive Engine",
        "timestamp": datetime.utcnow().isoformat(),
        "ai_operational_monitor": {
            "budget_status": ai_stats["budget_status"],
            "month_spend_usd": ai_stats["total_cost_usd"],
            "budget_limit_usd": ai_stats["budget_limit_usd"],
            "recent_evaluations": ai_stats["total_evaluations"],
            "discard_rate": ai_stats["discard_rate"],
            "discard_rate_alert": ai_stats["discard_rate_alert"]
        }
    }
    if not db_ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health_data
        )
    return health_data


@app.get(
    "/api/admin/ai-audit-stats",
    response_model=DiagnosticAuditStatsResponse,
    summary="Estadísticas consolidadas de auditoría operativa de IA y control de costos (Fase 7)"
)
def get_ai_audit_stats_endpoint(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retorna métricas de evaluación de IA: tasa de descarte, gasto mensual y alertas de deriva."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido a administradores del sistema."
        )
    from backend.services.ai_service import get_ai_audit_statistics
    stats = get_ai_audit_statistics(db, sample_size=100)
    return stats


# ==============================================================================
# 🔐 ENDPOINTS DE AUTENTICACIÓN Y GESTIÓN DE CUENTAS (JWT)
# ==============================================================================

@app.post(
    "/api/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una nueva cuenta de usuario"
)
def register_user(
    payload: UserRegister,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Crea una nueva cuenta de usuario, inicializa su primer acuario y emite token JWT con refresh token en cookie."""
    check_auth_rate_limit(request)
    normalized_email = payload.email.strip().lower()

    existing_user = db.query(User).filter(User.email == normalized_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una cuenta registrada con este correo electrónico."
        )

    # Rol de administrador NUNCA se asigna automáticamente por correo (P0.2)
    require_verification = os.getenv("REQUIRE_EMAIL_VERIFICATION", "false").lower() in ("true", "1", "yes")

    # Crear usuario con plan Gratuito (Freemium)
    new_user = User(
        email=normalized_email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name.strip() if payload.full_name else None,
        unit_preference="liters",
        subscription_tier="free",
        is_admin=False,
        is_active=False if require_verification else True,
        email_verified=False,
        created_at=datetime.utcnow()
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Generar token de verificación de correo
    verify_token = create_email_verification_token(new_user.email, new_user.id)
    frontend_base = os.getenv("FRONTEND_URL", "").rstrip("/") or "http://localhost:5173"
    verify_url = f"{frontend_base}/?verify_email_token={verify_token}"
    send_email_verification(new_user.email, verify_url)

    # Crear automáticamente su primer acuario por defecto
    default_tank = Tank(
        user_id=new_user.id,
        name="Mi Acuario Principal",
        tank_type="reef",
        volume_liters=280.0,
        notes="Acuario inicial creado automáticamente"
    )
    db.add(default_tank)
    db.commit()

    access_token = create_access_token({
        "sub": str(new_user.id),
        "email": new_user.email,
        "token_version": new_user.token_version or 1
    })
    refresh_token = create_refresh_token(new_user.id)

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_production,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/auth"
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        refresh_token=refresh_token,
        user=UserResponse.model_validate(new_user)
    )

@app.post(
    "/api/auth/login",
    response_model=TokenResponse,
    summary="Iniciar sesión con correo y contraseña"
)
def login_user(
    payload: UserLogin,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Valida credenciales y emite token JWT con refresh token en cookie HttpOnly. Evita enumeración de usuarios."""
    check_auth_rate_limit(request)
    normalized_email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas. Verifica tu correo y contraseña.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        if not user.email_verified and os.getenv("REQUIRE_EMAIL_VERIFICATION", "false").lower() in ("true", "1", "yes"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Debes verificar tu correo electrónico antes de activar tu cuenta. Hemos enviado un enlace a tu correo."
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta cuenta ha sido suspendida o no está activa. Contacta a soporte."
        )

    # Rol de administrador se asigna solo en BD (P0.2)

    access_token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "token_version": user.token_version or 1
    })
    refresh_token = create_refresh_token(user.id)

    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_production,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/auth"
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user)
    )

@app.post(
    "/api/auth/refresh",
    response_model=TokenResponse,
    summary="Renovar token de acceso usando refresh token rotativo en cookie o cabecera"
)
def refresh_access_token(
    request: Request,
    response: Response,
    x_refresh_token: Optional[str] = Header(None, alias="X-Refresh-Token"),
    db: Session = Depends(get_db)
):
    """Verifica el refresh token de la cookie HttpOnly (o cabecera) y rota emitiendo un nuevo par de tokens."""
    cookie_token = request.cookies.get("refresh_token")
    token_to_verify = cookie_token or x_refresh_token

    if not token_to_verify:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se proporcionó refresh token válido en cookie HttpOnly o cabecera X-Refresh-Token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = verify_refresh_token(token_to_verify)
    user_id = int(payload["sub"])
    user = db.query(User).filter(User.id == user_id).first()

    if not user or not user.is_active:
        response.delete_cookie(key="refresh_token", path="/api/auth")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión expirada o usuario inactivo. Inicie sesión nuevamente.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    new_access_token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "token_version": user.token_version or 1
    })
    new_refresh_token = create_refresh_token(user.id)

    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        secure=is_production,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/auth"
    )

    return TokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        refresh_token=new_refresh_token,
        user=UserResponse.model_validate(user)
    )

@app.post(
    "/api/auth/logout",
    summary="Cerrar sesión e invalidar la cookie del refresh token"
)
def logout_user(response: Response):
    """Limpia la cookie HttpOnly del refresh token."""
    response.delete_cookie(key="refresh_token", path="/api/auth")
    return {"status": "success", "message": "Sesión cerrada correctamente."}

@app.post(
    "/api/auth/forgot-password",
    response_model=PasswordResetResponse,
    summary="Solicitar enlace para restablecer contraseña"
)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Genera un token firmado temporal y emite un enlace de restablecimiento.
    Por seguridad (OWASP), siempre responde de manera neutral para evitar enumeración de correos.
    El token es de un solo uso y se envía por proveedor transaccional SMTP sin exponerlo en logs.
    """
    check_auth_rate_limit(request)
    normalized_email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()

    frontend_base = os.getenv("FRONTEND_URL", "").rstrip("/") or "http://localhost:5173"

    if user and user.is_active:
        reset_token, jti, expire = create_password_reset_token(user.email, user.id)
        reset_url = f"{frontend_base}/?reset_token={reset_token}"
        token_hash = hashlib.sha256(reset_token.encode("utf-8")).hexdigest()

        # Guardar registro en BD de un solo uso
        reset_record = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            jti=jti,
            expires_at=expire
        )
        db.add(reset_record)
        db.commit()

        # Envío seguro por correo transaccional (no se imprime token ni URL en logs)
        send_password_reset_email(user.email, reset_url)

    logger.info("Solicitud de restablecimiento de contraseña procesada con respuesta neutral.")
    return PasswordResetResponse(
        ok=True,
        message="Si tu correo está registrado, recibirás un enlace seguro para restablecer tu contraseña."
    )

@app.post(
    "/api/auth/reset-password",
    response_model=PasswordResetResponse,
    summary="Restablecer la contraseña usando el token seguro"
)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Valida el token firmado de un solo uso, actualiza contraseña con bcrypt e invalida todas las sesiones previas."""
    try:
        check_password_complexity(payload.new_password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    token_data = verify_password_reset_token(payload.token)
    user_id = int(token_data["sub"])
    jti = token_data.get("jti")

    # Validar un solo uso en BD
    reset_record = db.query(PasswordResetToken).filter(
        PasswordResetToken.jti == jti,
        PasswordResetToken.user_id == user_id
    ).first()

    now = datetime.now(timezone.utc)
    if not reset_record or reset_record.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este enlace de restablecimiento ya ha sido utilizado o no es válido. Solicita uno nuevo."
        )

    # Validar expiración contra BD
    exp = reset_record.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de restablecimiento ha expirado. Por favor solicita uno nuevo."
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta se encuentra suspendida. Contacta a soporte."
        )

    # 1. Actualizar contraseña
    user.hashed_password = hash_password(payload.new_password)
    # 2. Invalidar todas las sesiones previas incrementando token_version
    user.token_version = (user.token_version or 1) + 1
    # 3. Marcar token como utilizado
    reset_record.used_at = now
    db.commit()

    logger.info("Contraseña actualizada y sesiones anteriores revocadas para usuario.")

    return PasswordResetResponse(
        ok=True,
        message="Contraseña actualizada exitosamente. Ya puedes iniciar sesión con tu nueva contraseña."
    )

@app.api_route(
    "/api/auth/verify-email",
    methods=["GET", "POST"],
    summary="Verificar correo electrónico para activar la cuenta"
)
def verify_email(
    token: str = Query(..., description="Token JWT de verificación de correo"),
    db: Session = Depends(get_db)
):
    """Valida el token de verificación y activa la cuenta del usuario."""
    token_data = verify_email_verification_token(token)
    user_id = int(token_data["sub"])

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado."
        )

    user.email_verified = True
    user.is_active = True
    db.commit()

    logger.info(f"Correo electrónico verificado exitosamente para usuario ID {user.id}")
    return {
        "ok": True,
        "message": "Correo electrónico verificado exitosamente. Tu cuenta está activa y lista para usar."
    }

@app.get(
    "/api/auth/me",
    response_model=UserResponse,
    summary="Obtener perfil del usuario autenticado"
)
def get_user_profile(current_user: User = Depends(get_current_user)):
    """Retorna información del usuario autenticado actual."""
    return UserResponse.model_validate(current_user)

@app.put(
    "/api/auth/me",
    response_model=UserResponse,
    summary="Actualizar perfil y preferencias de la cuenta"
)
def update_user_profile(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Actualiza nombre o preferencia de unidades de medida (liters / gallons)."""
    if payload.full_name is not None:
        current_user.full_name = payload.full_name.strip()
    if payload.unit_preference is not None:
        current_user.unit_preference = payload.unit_preference

    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)


# ==============================================================================
# 📂 PRIVACIDAD Y DERECHOS DE USUARIO (GDPR / ARCO - EXPORTACIÓN Y BORRADO)
# ==============================================================================

@app.get(
    "/api/user/export",
    summary="Exportar todos los datos personales del usuario (Derecho de portabilidad GDPR)"
)
def export_user_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Genera una copia íntegra y portable de todos los datos del usuario en formato JSON."""
    tanks = db.query(Tank).filter(Tank.user_id == current_user.id).all()
    measurements = db.query(Measurement).filter(Measurement.user_id == current_user.id).all()
    tasks = db.query(MaintenanceTask).filter(MaintenanceTask.user_id == current_user.id).all()
    water_changes = db.query(WaterChange).filter(WaterChange.user_id == current_user.id).all()
    push_subs = db.query(PushSubscription).filter(PushSubscription.user_id == current_user.id).all()

    return {
        "exported_at": datetime.utcnow().isoformat(),
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "unit_preference": current_user.unit_preference,
            "subscription_tier": current_user.subscription_tier,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None
        },
        "tanks": [
            {
                "id": t.id,
                "name": t.name,
                "tank_type": t.tank_type,
                "volume_liters": t.volume_liters,
                "reef_profile": t.reef_profile,
                "dosing_method": t.dosing_method,
                "lighting_par": t.lighting_par,
                "flow_profile": t.flow_profile,
                "notes": t.notes,
                "created_at": t.created_at.isoformat() if t.created_at else None
            }
            for t in tanks
        ],
        "measurements": [
            {
                "id": m.id,
                "tank_id": m.tank_id,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                "ph": m.ph,
                "kh": m.kh,
                "calcium": m.calcium,
                "magnesium": m.magnesium,
                "nitrate": m.nitrate,
                "phosphate": m.phosphate,
                "salinity": m.salinity,
                "temperature": m.temperature,
                "ammonia": m.ammonia,
                "nitrite": m.nitrite,
                "trace_elements": m.trace_elements,
                "test_methods": m.test_methods,
                "notes": m.notes
            }
            for m in measurements
        ],
        "maintenance_tasks": [
            {
                "id": task.id,
                "aquarium_id": task.aquarium_id,
                "task_key": task.task_key,
                "title": task.title,
                "category": task.category,
                "frequency_days": task.frequency_days,
                "last_completed_at": task.last_completed_at.isoformat() if task.last_completed_at else None,
                "next_due_at": task.next_due_at.isoformat() if task.next_due_at else None,
                "is_enabled": task.is_enabled,
                "notes": task.notes
            }
            for task in tasks
        ],
        "water_changes": [
            {
                "id": wc.id,
                "tank_id": wc.tank_id,
                "volume_liters": wc.volume_liters,
                "percentage": wc.percentage,
                "performed_at": wc.performed_at.isoformat() if wc.performed_at else None,
                "notes": wc.notes
            }
            for wc in water_changes
        ],
        "push_subscriptions": [
            {
                "id": ps.id,
                "endpoint": ps.endpoint,
                "notify_maintenance": ps.notify_maintenance,
                "notify_alerts": ps.notify_alerts,
                "created_at": ps.created_at.isoformat() if ps.created_at else None
            }
            for ps in push_subs
        ]
    }

@app.delete(
    "/api/user/account",
    summary="Eliminar permanentemente la cuenta de usuario y todos los datos asociados (Derecho al olvido GDPR)"
)
def delete_user_account(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Elimina en cascada estricta el usuario y absolutamente todos sus registros asociados."""
    user_id = current_user.id
    email = current_user.email
    db.delete(current_user)
    db.commit()

    response.delete_cookie(key="refresh_token", path="/api/auth")
    logger.info(f"Cuenta y datos eliminados íntegramente para el usuario {email} (ID: {user_id}).")
    return {
        "status": "success",
        "message": "Tu cuenta y todos tus datos (tanques, mediciones, tareas, cambios de agua) han sido eliminados de forma permanente."
    }


# ==============================================================================
# 🛡️ ENDPOINTS DE ADMINISTRACIÓN (SOLO USUARIOS CON IS_ADMIN = TRUE)
# ==============================================================================

@app.get(
    "/api/admin/users",
    response_model=List[AdminUserListItem],
    summary="Listar todos los usuarios registrados con métricas (Solo Admin)"
)
def admin_list_users(
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Retorna el listado consolidado de usuarios, acuarios y estado de cuentas."""
    users = db.query(User).order_by(User.id.asc()).all()
    results = []
    for u in users:
        t_count = db.query(Tank).filter(Tank.user_id == u.id).count()
        m_count = db.query(Measurement).filter(Measurement.user_id == u.id).count()
        results.append(
            AdminUserListItem(
                id=u.id,
                email=u.email,
                full_name=u.full_name,
                unit_preference=u.unit_preference or "liters",
                subscription_tier=u.subscription_tier or "free",
                is_admin=bool(u.is_admin),
                is_active=bool(u.is_active),
                tank_count=t_count,
                measurement_count=m_count,
                created_at=u.created_at
            )
        )
    return results

@app.put(
    "/api/admin/users/{user_id}",
    response_model=AdminUserListItem,
    summary="Modificar límites de plan, suspender cuenta o cambiar rol (Solo Admin)"
)
def admin_update_user(
    user_id: int,
    payload: AdminUserUpdate,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Permite suspender cuentas, cambiar plan Freemium (free/premium) o asignar permisos de admin."""
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado en la base de datos."
        )

    # Reglas de autoprotección para el admin en sesión
    if target_user.id == current_admin.id:
        if payload.is_active is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No puedes suspender tu propia cuenta de administrador."
            )
        if payload.is_admin is False:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No puedes remover tu propio rol de administrador."
            )

    if payload.subscription_tier is not None:
        target_user.subscription_tier = payload.subscription_tier
    if payload.is_active is not None:
        target_user.is_active = payload.is_active
    if payload.is_admin is not None:
        target_user.is_admin = payload.is_admin
    if payload.full_name is not None:
        target_user.full_name = payload.full_name.strip()

    db.commit()
    db.refresh(target_user)

    t_count = db.query(Tank).filter(Tank.user_id == target_user.id).count()
    m_count = db.query(Measurement).filter(Measurement.user_id == target_user.id).count()

    return AdminUserListItem(
        id=target_user.id,
        email=target_user.email,
        full_name=target_user.full_name,
        unit_preference=target_user.unit_preference or "liters",
        subscription_tier=target_user.subscription_tier or "free",
        is_admin=bool(target_user.is_admin),
        is_active=bool(target_user.is_active),
        tank_count=t_count,
        measurement_count=m_count,
        created_at=target_user.created_at
    )

@app.delete(
    "/api/admin/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar usuario y todos sus datos en cascada (Solo Admin)"
)
def admin_delete_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Elimina permanentemente al usuario y sus acuarios asociados."""
    if user_id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes eliminar tu propia cuenta de administrador."
        )

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado."
        )

    db.delete(target_user)
    db.commit()
    return None


# ==============================================================================
# 🐠 ENDPOINTS DE ACUARIOS (TANKS) AISLADOS POR USUARIO
# ==============================================================================

@app.get(
    "/api/tanks",
    response_model=List[TankResponse],
    summary="Listar acuarios pertenecientes al usuario activo"
)
def get_user_tanks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retorna únicamente los tanques pertenecientes al usuario autenticado."""
    tanks = db.query(Tank).filter(Tank.user_id == current_user.id).all()
    if not tanks:
        # Si el usuario no tiene tanque, crear uno predeterminado
        first_tank = Tank(
            user_id=current_user.id,
            name="Mi Acuario Principal",
            tank_type="reef",
            volume_liters=280.0
        )
        db.add(first_tank)
        db.commit()
        db.refresh(first_tank)
        tanks = [first_tank]

    return [TankResponse.model_validate(t) for t in tanks]

@app.post(
    "/api/tanks",
    response_model=TankResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo acuario para el usuario activo"
)
def create_user_tank(
    payload: TankCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Crea un acuario nuevo vinculado estrictamente al user_id activo."""
    # Control Freemium: Límite de 1 acuario en Plan Free
    if current_user.subscription_tier == "free":
        tank_count = db.query(Tank).filter(Tank.user_id == current_user.id).count()
        if tank_count >= 1:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El plan Free permite gestionar 1 acuario. Haz upgrade a Premium para tanques ilimitados."
            )

    new_tank = Tank(
        user_id=current_user.id,
        name=payload.name.strip(),
        tank_type=payload.tank_type,
        volume_liters=payload.volume_liters,
        reef_profile=payload.reef_profile,
        dosing_method=payload.dosing_method,
        lighting_par=payload.lighting_par,
        flow_profile=payload.flow_profile,
        notes=payload.notes
    )
    db.add(new_tank)
    db.commit()
    db.refresh(new_tank)
    try:
        seed_default_maintenance_tasks(db, new_tank)
    except Exception as e:
        logger.warning(f"Aviso al sembrar tareas de mantenimiento para tanque {new_tank.id}: {e}")
    try:
        seed_default_maintenance_tasks(db, new_tank)
    except Exception as e:
        logger.warning(f"Aviso al sembrar tareas de mantenimiento para tanque {new_tank.id}: {e}")
    return TankResponse.model_validate(new_tank)

@app.post(
    "/api/aquariums",
    response_model=TankResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo acuario",
    tags=["Acuarios"]
)
@app.post("/api/acuarios", include_in_schema=False)
def create_aquarium_via_schema(
    payload: AquariumCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo acuario utilizando el esquema AquariumCreate vinculado estrictamente al usuario autenticado.
    """
    user_id = current_user.id
    new_tank = Tank(
        user_id=user_id,
        name=payload.name.strip(),
        tank_type=payload.tank_type,
        volume_liters=float(payload.volume_liters),
        reef_profile=payload.reef_profile,
        dosing_method=payload.dosing_method,
        lighting_par=payload.lighting_par,
        flow_profile=payload.flow_profile,
        notes=payload.notes
    )
    db.add(new_tank)
    db.commit()
    db.refresh(new_tank)
    try:
        seed_default_maintenance_tasks(db, new_tank)
    except Exception as e:
        logger.warning(f"Aviso al sembrar tareas de mantenimiento para tanque {new_tank.id}: {e}")

    # Sincronización en tabla acuarios
    try:
        nuevo_acuario = Acuario(
            id=new_tank.id,
            nombre=new_tank.name,
            volumen_litros=new_tank.volume_liters,
            usuario_id=str(user_id),
            reef_profile=new_tank.reef_profile,
            dosing_method=new_tank.dosing_method,
            lighting_par=new_tank.lighting_par,
            flow_profile=new_tank.flow_profile
        )
        db.add(nuevo_acuario)
        db.commit()
    except Exception:
        db.rollback()

    return TankResponse.model_validate(new_tank)

@app.put(
    "/api/aquariums/{aquarium_id}",
    summary="Actualizar litraje del acuario",
    tags=["Acuarios"]
)
@app.put("/api/acuarios/{aquarium_id}", include_in_schema=False)
@app.put("/api/tanks/{aquarium_id}", include_in_schema=False)
def update_aquarium(
    aquarium_id: int,
    volume_liters: Optional[int] = Query(None, description="Nuevo volumen en litros"),
    payload: Optional[dict] = Body(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Actualiza el volumen en litros y parámetros de un acuario verificando que pertenezca al usuario autenticado (Anti-IDOR).
    """
    actual_volume = volume_liters
    if actual_volume is None and payload and "volume_liters" in payload:
        actual_volume = payload["volume_liters"]
    elif actual_volume is None and isinstance(payload, (int, float)):
        actual_volume = payload

    if actual_volume is None and not (payload and any(k in payload for k in ["name", "tank_type", "type", "notes", "reef_profile", "dosing_method", "lighting_par", "flow_profile"])):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Se requiere el campo 'volume_liters' o datos a actualizar")

    # Validación estricta anti-IDOR: verificar pertenencia a current_user.id
    tank = db.query(Aquarium).filter(Aquarium.id == aquarium_id, Aquarium.user_id == current_user.id).first()
    if not tank:
        try:
            legacy_acuario = db.query(Acuario).filter(Acuario.id == aquarium_id, Acuario.usuario_id == str(current_user.id)).first()
            if legacy_acuario:
                tank = legacy_acuario
        except Exception:
            db.rollback()

    if not tank:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Acuario no encontrado o no pertenece a tu cuenta."
        )

    if actual_volume is not None:
        tank.volume_liters = actual_volume

    if payload and isinstance(payload, dict):
        if "name" in payload and payload["name"]:
            tank.name = str(payload["name"]).strip()
        if "tank_type" in payload and payload["tank_type"]:
            tank.tank_type = str(payload["tank_type"]).strip()
        elif "type" in payload and payload["type"]:
            tank.tank_type = str(payload["type"]).strip()
        if "reef_profile" in payload:
            tank.reef_profile = payload["reef_profile"]
        if "dosing_method" in payload:
            tank.dosing_method = payload["dosing_method"]
        if "lighting_par" in payload:
            tank.lighting_par = int(payload["lighting_par"]) if payload["lighting_par"] is not None and str(payload["lighting_par"]).strip() != "" else None
        if "flow_profile" in payload:
            tank.flow_profile = payload["flow_profile"]
        if "notes" in payload:
            tank.notes = payload["notes"]

    # Sincronización entre tablas tanks y acuarios si coexisten
    if isinstance(tank, Tank):
        acuario_record = db.query(Acuario).filter(Acuario.id == aquarium_id).first()
        if acuario_record:
            if actual_volume is not None:
                acuario_record.volumen_litros = actual_volume
            if hasattr(tank, "name"):
                acuario_record.nombre = tank.name
            acuario_record.reef_profile = getattr(tank, "reef_profile", None)
            acuario_record.dosing_method = getattr(tank, "dosing_method", None)
            acuario_record.lighting_par = getattr(tank, "lighting_par", None)
            acuario_record.flow_profile = getattr(tank, "flow_profile", None)
    elif isinstance(tank, Acuario):
        tank_record = db.query(Tank).filter(Tank.id == aquarium_id).first()
        if tank_record:
            if actual_volume is not None:
                tank_record.volume_liters = actual_volume
            if hasattr(tank, "nombre"):
                tank_record.name = tank.nombre
            tank_record.reef_profile = getattr(tank, "reef_profile", None)
            tank_record.dosing_method = getattr(tank, "dosing_method", None)
            tank_record.lighting_par = getattr(tank, "lighting_par", None)
            tank_record.flow_profile = getattr(tank, "flow_profile", None)

    db.commit()
    db.refresh(tank)
    return {
        "message": "Acuario actualizado",
        "new_volume": getattr(tank, "volume_liters", actual_volume),
        "tank_type": getattr(tank, "tank_type", None),
        "id": tank.id,
        "name": getattr(tank, "name", None) or getattr(tank, "nombre", None),
        "volume_liters": getattr(tank, "volume_liters", actual_volume),
        "reef_profile": getattr(tank, "reef_profile", None),
        "dosing_method": getattr(tank, "dosing_method", None),
        "lighting_par": getattr(tank, "lighting_par", None),
        "flow_profile": getattr(tank, "flow_profile", None),
        "notes": getattr(tank, "notes", None)
    }

@app.delete(
    "/api/tanks/{tank_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un acuario del usuario"
)
def delete_user_tank(
    tank_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Elimina el acuario verificando estricta pertenencia al usuario."""
    tank = db.query(Tank).filter(Tank.id == tank_id, Tank.user_id == current_user.id).first()
    if not tank:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Acuario no encontrado o no pertenece a tu cuenta."
        )
    db.delete(tank)
    db.commit()
    return None


# ==============================================================================
# 📊 ENDPOINTS DE MEDICIONES (MEASUREMENTS) AISLADOS POR USUARIO
# ==============================================================================

@app.post(
    "/api/measurements",
    response_model=MeasurementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Guardar una nueva medición vinculada al usuario activo"
)
@app.post(
    "/api/parameter_logs",
    response_model=MeasurementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Guardar una nueva medición vinculada al usuario activo (alias parameter_logs)"
)
def create_measurement(
    payload: MeasurementCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Guarda una medición vinculada estrictamente al user_id del usuario autenticado.
    Si se especifica tank_id, verifica que pertenezca al usuario.
    Si el motor de reglas detecta alerta crítica o advertencia grave, dispara notificación push vía BackgroundTasks.
    """
    # Control de idempotencia (Fase 5 - Cola Offline PWA)
    if payload.client_uuid:
        existing_meas = db.query(Measurement).filter(
            Measurement.client_uuid == payload.client_uuid,
            Measurement.user_id == current_user.id
        ).first()
        if existing_meas:
            logger.info(f"Medición idempotente detectada ({payload.client_uuid}). Retornando existente.")
            return MeasurementResponse.model_validate(existing_meas)

    measurement_time = payload.timestamp or datetime.utcnow()
    target_tank_id = payload.tank_id

    if target_tank_id:
        tank_exists = db.query(Tank).filter(
            Tank.id == target_tank_id,
            Tank.user_id == current_user.id
        ).first()
        if not tank_exists:
            target_tank_id = None

    if not target_tank_id:
        user_tank = db.query(Tank).filter(Tank.user_id == current_user.id).first()
        if not user_tank:
            user_tank = Tank(
                user_id=current_user.id,
                name="Mi Acuario Principal",
                tank_type="reef",
                volume_liters=280.0
            )
            db.add(user_tank)
            db.commit()
            db.refresh(user_tank)
        target_tank_id = user_tank.id

    temp_val = payload.temperature if payload.temperature is not None else payload.temperatura
    kh_val = payload.kh if payload.kh is not None else payload.alkalinity_dkh
    ca_val = payload.calcium if payload.calcium is not None else (payload.calcium_ppm if payload.calcium_ppm is not None else payload.calcio)
    mg_val = payload.magnesium if payload.magnesium is not None else (payload.magnesium_ppm if payload.magnesium_ppm is not None else payload.magnesio)
    no3_val = payload.nitrate if payload.nitrate is not None else (payload.nitrate_ppm if payload.nitrate_ppm is not None else payload.nitrato)
    po4_val = payload.phosphate if payload.phosphate is not None else (payload.phosphate_ppm if payload.phosphate_ppm is not None else payload.fosfato)
    sal_val = payload.salinity if payload.salinity is not None else payload.salinity_ppt
    nh3_val = payload.ammonia if payload.ammonia is not None else payload.ammonia_ppm
    no2_val = payload.nitrite if payload.nitrite is not None else payload.nitrite_ppm

    db_measurement = Measurement(
        user_id=current_user.id,
        tank_id=target_tank_id,
        timestamp=measurement_time,
        ph=payload.ph,
        alkalinity_dkh=kh_val,
        kh=kh_val,
        calcium_ppm=ca_val,
        calcium=ca_val,
        magnesium_ppm=mg_val,
        magnesium=mg_val,
        nitrate_ppm=no3_val,
        nitrate=no3_val,
        phosphate_ppm=po4_val,
        phosphate=po4_val,
        salinity_ppt=sal_val,
        salinity=sal_val,
        temperature=temp_val,
        temperatura=temp_val,
        ammonia=nh3_val,
        nitrite=no2_val,
        trace_elements=payload.trace_elements,
        test_methods=payload.test_methods,
        notes=payload.notes,
        kit=payload.kit,
        is_camera_scan=payload.is_camera_scan or False,
        is_draft=payload.is_draft or False,
        client_uuid=payload.client_uuid
    )
    db.add(db_measurement)
    db.commit()
    db.refresh(db_measurement)

    # Disparo asíncrono no bloqueante de alertas críticas por Web Push
    try:
        background_tasks.add_task(
            check_and_notify_measurement_alert,
            user_id=current_user.id,
            tank_id=target_tank_id,
            measurement_id=db_measurement.id
        )
    except Exception as bg_err:
        logger.warning(f"Aviso programando tarea push en background: {bg_err}")

    return db_measurement

@app.post(
    "/api/tanks/{tank_id}/measurements",
    response_model=MeasurementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Guardar una nueva medición vinculada a un acuario específico"
)
def create_tank_measurement(
    tank_id: int,
    payload: MeasurementCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Guarda una medición vinculada al acuario especificado por tank_id y al usuario activo.
    """
    tank = db.query(Tank).filter(Tank.id == tank_id, Tank.user_id == current_user.id).first()
    if not tank:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Acuario no encontrado o no pertenece a tu cuenta."
        )
    payload.tank_id = tank_id
    return create_measurement(
        payload=payload,
        background_tasks=background_tasks,
        current_user=current_user,
        db=db
    )

@app.get(
    "/api/tanks/{tank_id}/measurements",
    response_model=List[MeasurementResponse],
    summary="Listar mediciones de un acuario específico"
)
def get_tank_measurements(
    tank_id: int,
    limit: int = Query(100, ge=1, le=500, description="Número máximo de registros"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="Orden cronológico"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retorna las mediciones pertenecientes al acuario especificado y al usuario activo."""
    tank = db.query(Tank).filter(Tank.id == tank_id, Tank.user_id == current_user.id).first()
    if not tank:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Acuario no encontrado o no pertenece a tu cuenta."
        )
    query = db.query(Measurement).filter(
        Measurement.user_id == current_user.id,
        Measurement.tank_id == tank_id
    )
    if order == "desc":
        query = query.order_by(Measurement.timestamp.desc())
    else:
        query = query.order_by(Measurement.timestamp.asc())
    return query.limit(limit).all()

@app.get(
    "/api/measurements",
    response_model=List[MeasurementResponse],
    summary="Obtener historial de mediciones exclusivo del usuario activo"
)
def get_measurements(
    limit: int = Query(100, ge=1, le=500, description="Número máximo de registros"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="Orden cronológico"),
    tank_id: Optional[int] = Query(None, description="Filtrar por acuario específico"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retorna únicamente las mediciones pertenecientes al usuario autenticado."""
    if tank_id:
        tank = db.query(Tank).filter(Tank.id == tank_id, Tank.user_id == current_user.id).first()
        if not tank:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Acuario no encontrado o no pertenece a tu cuenta."
            )
    query = db.query(Measurement).filter(Measurement.user_id == current_user.id)
    if tank_id:
        query = query.filter(Measurement.tank_id == tank_id)

    if order == "asc":
        query = query.order_by(Measurement.timestamp.asc())
    else:
        query = query.order_by(Measurement.timestamp.desc())

    return query.limit(limit).all()

@app.get(
    "/api/predictions",
    response_model=PredictionResponse,
    summary="Cálculo predictivo sobre los datos del usuario activo"
)
def get_predictions(
    tank_id: Optional[int] = Query(None, description="Filtrar por acuario"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Calcula predicciones de consumo y cambios de agua exclusivamente para el usuario activo."""
    if tank_id:
        tank = db.query(Tank).filter(Tank.id == tank_id, Tank.user_id == current_user.id).first()
        if not tank:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Acuario no encontrado o no pertenece a tu cuenta."
            )
    query = db.query(Measurement).filter(Measurement.user_id == current_user.id)
    if tank_id:
        query = query.filter(Measurement.tank_id == tank_id)

    measurements = query.order_by(Measurement.timestamp.asc()).all()
    predictions = calculate_predictions(measurements)
    return predictions


# ==============================================================================
# 📷 ENDPOINT DE VISIÓN ARTIFICIAL (IA VISION)
# ==============================================================================
# 📷 ENDPOINTS DE VISIÓN ARTIFICIAL (IA VISION & CUOTA)
# ==============================================================================

@app.get(
    "/api/scan-quota",
    summary="Consultar cuota restante de escaneos IA del usuario"
)
def get_user_scan_quota(
    current_user: User = Depends(get_current_user)
):
    """
    Retorna la información de cuota diaria y escaneos restantes del usuario autenticado.
    No consume ninguna cuota.
    """
    return scan_quota_manager.get_quota_info(
        user_id=current_user.id,
        subscription_tier=current_user.subscription_tier,
        is_admin=current_user.is_admin
    )

@app.post(
    "/api/scan-measurement",
    response_model=ScanMeasurementResponse,
    summary="Escanear fotografía de test kit con modelo de visión IA"
)
def scan_measurement_photo(
    payload: ScanMeasurementRequest,
    response: Response,
    current_user: User = Depends(get_current_user)
):
    """
    Recibe una fotografía en Base64 tomada por el móvil, la procesa mediante
    Google Gemini Vision e identifica el parámetro, valor numérico y test kit.
    Requiere autenticación activa del usuario.
    Aplica:
    1. Rate limit y cuota diaria por usuario para proteger costos de Gemini.
    2. Validación de magic bytes (JPEG/PNG/WebP), máx. 5 MB, re-codificación con Pillow y purga de EXIF/GPS.
    3. Tratamiento del texto en la imagen como dato observacional, nunca instrucción.
    4. Toda respuesta es un borrador no persistido en BD que requiere revisión humana.
    """
    # 1. Aplicar rate limit y cuota diaria por usuario
    quota_info = scan_quota_manager.check_and_consume(
        user_id=current_user.id,
        subscription_tier=current_user.subscription_tier,
        is_admin=current_user.is_admin
    )

    # Cabeceras de rate limiting en la respuesta
    response.headers["X-RateLimit-Limit"] = str(quota_info["daily_quota"])
    response.headers["X-RateLimit-Remaining"] = str(quota_info["remaining_today"])
    response.headers["X-RateLimit-Reset"] = str(quota_info["reset_seconds"])

    try:
        result = analyze_test_image(
            image_data=payload.image_base64,
            preferred_parameter=payload.preferred_parameter,
            allow_demo_fallback=payload.demo_fallback,
            save_image=payload.save_image
        )
        result.remaining_scans_today = quota_info["remaining_today"]
        result.daily_quota = quota_info["daily_quota"]
        return result
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al analizar la imagen: {str(e)}"
        )


# ==============================================================================
# 🧠 ENDPOINTS DE ANÁLISIS PREDICTIVO CLÍNICO CON IA (GEMINI)
# ==============================================================================

router = APIRouter()

@router.post(
    "/api/analisis-predictivo",
    response_model=PredictiveAnalysisJsonResponse,
    summary="Obtener análisis predictivo estructurado en JSON (AquaPulse AI)"
)
def obtener_analisis_json(
    data: AquariumDataRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Endpoint estructurado para obtener diagnóstico predictivo en formato JSON puro.
    Ejecuta inferencia técnica con Gemini mediante esquemas tipados verificando pertenencia de datos (Anti-IDOR).
    Si se especifica acuario_id o tank_id, consulta automáticamente el historial real de las últimas 48h.
    """
    if data.is_draft:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lectura de cámara en estado borrador (sin confirmar): toda lectura por visión es un borrador que el usuario debe confirmar o corregir antes de usarse en un diagnóstico."
        )

    try:
        data_dict = data.model_dump() if hasattr(data, "model_dump") else data.dict()
        target_id = data.acuario_id or data.tank_id
        if target_id:
            tank_obj = db.query(Tank).filter(Tank.id == target_id, Tank.user_id == current_user.id).first()
            if not tank_obj:
                try:
                    legacy_acuario = db.query(Acuario).filter(Acuario.id == target_id, Acuario.usuario_id == str(current_user.id)).first()
                    if legacy_acuario:
                        tank_obj = legacy_acuario
                except Exception:
                    db.rollback()

            if not tank_obj:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Acuario no encontrado o no pertenece a tu cuenta."
                )

            if not data.tendencia_reciente or data.tendencia_reciente in ["Estable en las últimas 24h", "Estable"]:
                historial_48h = obtener_tendencia_ultimas_48h(db, target_id)
                data_dict["tendencia_reciente"] = historial_48h

            db_type = getattr(tank_obj, "tank_type", None) or getattr(tank_obj, "tipo", None)
            if db_type and (not data_dict.get("tipo") or data_dict.get("tipo") == "mixto"):
                data_dict["tipo"] = db_type
                data_dict["tank_type"] = db_type
            if not data_dict.get("reef_profile"):
                data_dict["reef_profile"] = getattr(tank_obj, "reef_profile", None)
            if not data_dict.get("dosing_method"):
                data_dict["dosing_method"] = getattr(tank_obj, "dosing_method", None)
            if not data_dict.get("lighting_par"):
                data_dict["lighting_par"] = getattr(tank_obj, "lighting_par", None)
            if not data_dict.get("flow_profile"):
                data_dict["flow_profile"] = getattr(tank_obj, "flow_profile", None)

            # Extraer mediciones recientes para evaluación de alertas de delta KH y dosificación (excluyendo borradores no confirmados)
            recent_meas = (
                db.query(Measurement)
                .filter(
                    Measurement.tank_id == target_id,
                    Measurement.user_id == current_user.id,
                    (Measurement.is_draft == False) | (Measurement.is_draft == None)
                )
                .order_by(Measurement.timestamp.desc())
                .limit(20)
                .all()
            )
            if recent_meas:
                data_dict["history_measurements"] = [
                    {
                        "timestamp": m.timestamp.isoformat() if hasattr(m.timestamp, "isoformat") else str(m.timestamp),
                        "kh": m.kh or m.alkalinity_dkh,
                        "temperature": m.temperature or m.temperatura,
                        "ph": m.ph,
                        "calcium": m.calcium or m.calcium_ppm,
                        "magnesium": m.magnesium or m.magnesium_ppm,
                        "nitrate": m.nitrate or m.nitrate_ppm,
                        "phosphate": m.phosphate or m.phosphate_ppm,
                    }
                    for m in recent_meas
                ]

            # Extraer tareas de mantenimiento activas para correlación diagnóstica con IA
            active_maint = db.query(MaintenanceTask).filter(
                MaintenanceTask.aquarium_id == target_id,
                MaintenanceTask.user_id == current_user.id,
                MaintenanceTask.is_enabled == True
            ).all()
            if active_maint:
                data_dict["maintenance_tasks_summary"] = [
                    task_to_response_dict(t) for t in active_maint
                ]

        resultado_estructurado = analizar_parametros_estructurado(
            data_dict,
            db=db,
            user_id=current_user.id,
            tank_id=target_id
        )
        return {"status": "success", "data": resultado_estructurado}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en obtener_analisis_json: {e}. Activando fallback determinístico sin error 500.")
        from backend.ai_validator import generate_rules_deterministic_diagnosis
        fallback_res = generate_rules_deterministic_diagnosis(
            aquarium_name=data.nombre_acuario or "Principal",
            biotope=data.tipo or "Acuario",
            rules_alerts=[{"parameter": "diagnóstico", "status": "safe", "severity": "watch", "message": "Diagnóstico de respaldo determinístico por reglas de seguridad."}],
            measured_intervals=[]
        )
        return {"status": "success", "data": fallback_res}

@router.get(
    "/api/tanks/{tank_id}/tendencia-48h",
    summary="Obtener resumen textual del historial de mediciones de las últimas 48h"
)
@router.get(
    "/api/acuarios/{acuario_id}/tendencia-48h",
    summary="Obtener resumen textual del historial de mediciones de las últimas 48h (alias español)"
)
def endpoint_tendencia_48h(
    tank_id: Optional[int] = None,
    acuario_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Consulta las mediciones registradas en las últimas 48h verificando que el tanque pertenezca al usuario (Anti-IDOR)."""
    target_id = tank_id or acuario_id
    if not target_id:
        raise HTTPException(status_code=400, detail="Debe proporcionarse el ID del acuario.")

    tank = db.query(Tank).filter(Tank.id == target_id, Tank.user_id == current_user.id).first()
    if not tank:
        try:
            legacy_acuario = db.query(Acuario).filter(Acuario.id == target_id, Acuario.usuario_id == str(current_user.id)).first()
            if legacy_acuario:
                tank = legacy_acuario
        except Exception:
            db.rollback()

    if not tank:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Acuario no encontrado o no pertenece a tu cuenta."
        )

    resumen = obtener_tendencia_ultimas_48h(db, target_id)
    return {"status": "success", "acuario_id": target_id, "tendencia": resumen}

@router.post(
    "/api/acuarios/{acuario_id}/analisis-predictivo",
    response_model=PredictiveAnalysisJsonResponse,
    summary="Análisis predictivo con IA inyectando historial de 48h desde base de datos"
)
@router.post(
    "/api/tanks/{tank_id}/analisis-predictivo",
    response_model=PredictiveAnalysisJsonResponse,
    summary="Análisis predictivo con IA inyectando historial de 48h desde base de datos (alias tanks)"
)
def endpoint_analisis_con_historial(
    acuario_id: Optional[int] = None,
    tank_id: Optional[int] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    target_id = acuario_id or tank_id
    if not target_id:
        raise HTTPException(status_code=400, detail="Debe especificarse el ID del acuario.")

    tank_obj = db.query(Tank).filter(Tank.id == target_id, Tank.user_id == current_user.id).first()
    if not tank_obj:
        try:
            legacy_acuario = db.query(Acuario).filter(Acuario.id == target_id, Acuario.usuario_id == str(current_user.id)).first()
            if legacy_acuario:
                tank_obj = legacy_acuario
        except Exception:
            db.rollback()

    if not tank_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Acuario no encontrado o no pertenece a tu cuenta."
        )

    try:
        # 1. Obtener la última medición actual del acuario
        ultima_medicion = (
            db.query(Measurement)
            .filter(Measurement.tank_id == target_id, Measurement.user_id == current_user.id)
            .order_by(Measurement.timestamp.desc())
            .first()
        )

        if not ultima_medicion:
            ultima_medicion = (
                db.query(MedicionAcuario)
                .filter(MedicionAcuario.acuario_id == target_id)
                .order_by(MedicionAcuario.fecha_registro.desc())
                .first()
            )

        if not ultima_medicion:
            raise HTTPException(status_code=404, detail="No se encontraron mediciones para este acuario.")

        # 2. Extraer el historial de las últimas 48 horas usando la función anterior
        tendencia = obtener_tendencia_ultimas_48h(db, target_id)

        # 3. Preparar el paquete de datos para la IA
        nombre_acuario = getattr(tank_obj, "nombre", None) or getattr(tank_obj, "name", "Principal") if tank_obj else "Principal"
        volumen_litros = float(getattr(tank_obj, "volumen", None) or getattr(tank_obj, "volume_liters", 280.0) if tank_obj else 280.0)
        tipo_acuario = getattr(tank_obj, "tank_type", None) or getattr(tank_obj, "tipo", "mixto") if tank_obj else "mixto"

        recent_meas = (
            db.query(Measurement)
            .filter(Measurement.tank_id == target_id, Measurement.user_id == current_user.id)
            .order_by(Measurement.timestamp.desc())
            .limit(20)
            .all()
        )
        hist_list = []
        if recent_meas:
            hist_list = [
                {
                    "timestamp": m.timestamp.isoformat() if hasattr(m.timestamp, "isoformat") else str(m.timestamp),
                    "kh": m.kh or m.alkalinity_dkh,
                    "temperature": m.temperature or m.temperatura,
                    "ph": m.ph,
                    "calcium": m.calcium or m.calcium_ppm,
                    "magnesium": m.magnesium or m.magnesium_ppm,
                    "nitrate": m.nitrate or m.nitrate_ppm,
                    "phosphate": m.phosphate or m.phosphate_ppm,
                }
                for m in recent_meas
            ]

        datos_para_ia = {
            "nombre_acuario": nombre_acuario,
            "volumen_litros": volumen_litros,
            "tipo": tipo_acuario,
            "tank_type": tipo_acuario,
            "reef_profile": getattr(tank_obj, "reef_profile", None),
            "dosing_method": getattr(tank_obj, "dosing_method", None),
            "lighting_par": getattr(tank_obj, "lighting_par", None),
            "flow_profile": getattr(tank_obj, "flow_profile", None),
            "ph": ultima_medicion.ph,
            "kh": getattr(ultima_medicion, "kh", None) or getattr(ultima_medicion, "alkalinity_dkh", None),
            "calcio": getattr(ultima_medicion, "calcium", None) or getattr(ultima_medicion, "calcium_ppm", None) or getattr(ultima_medicion, "calcio", None),
            "magnesio": getattr(ultima_medicion, "magnesium", None) or getattr(ultima_medicion, "magnesium_ppm", None) or getattr(ultima_medicion, "magnesio", None),
            "nitrato": getattr(ultima_medicion, "nitrate", None) or getattr(ultima_medicion, "nitrate_ppm", None) or getattr(ultima_medicion, "nitrato", None),
            "fosfato": getattr(ultima_medicion, "phosphate", None) or getattr(ultima_medicion, "phosphate_ppm", None) or getattr(ultima_medicion, "fosfato", None),
            "temperatura": getattr(ultima_medicion, "temperature", None) or getattr(ultima_medicion, "temperatura", None),
            "salinity": getattr(ultima_medicion, "salinity", None) or getattr(ultima_medicion, "salinity_ppt", None),
            "ammonia": getattr(ultima_medicion, "ammonia", None),
            "nitrite": getattr(ultima_medicion, "nitrite", None),
            "trace_elements": getattr(ultima_medicion, "trace_elements", None),
            "test_methods": getattr(ultima_medicion, "test_methods", None),
            "tendencia_reciente": tendencia,
            "history_measurements": hist_list,
            "maintenance_tasks_summary": [
                task_to_response_dict(t) for t in db.query(MaintenanceTask).filter(
                    MaintenanceTask.aquarium_id == target_id,
                    MaintenanceTask.user_id == current_user.id,
                    MaintenanceTask.is_enabled == True
                ).all()
            ]
        }

        # 4. Llamar a la función de IA estructurada con verificación y fallback
        resultado_ia = analizar_acuario_estructurado(datos_para_ia)

        return {"status": "success", "data": resultado_ia}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint_analisis_con_historial: {e}. Activando fallback determinístico sin error 500.")
        from backend.ai_validator import generate_rules_deterministic_diagnosis
        fallback_res = generate_rules_deterministic_diagnosis(
            aquarium_name=getattr(tank_obj, "name", "Principal") if tank_obj else "Principal",
            biotope=getattr(tank_obj, "tank_type", "mixto") if tank_obj else "mixto",
            rules_alerts=[{"parameter": "diagnóstico", "status": "safe", "severity": "watch", "message": "Diagnóstico de respaldo determinístico por reglas de seguridad."}],
            measured_intervals=[]
        )
        return {"status": "success", "data": fallback_res}

app.include_router(router)

@app.post(
    "/api/analizar-ia",
    response_model=AquariumAnalysisResponse,
    summary="Analizar parámetros químicos y prever colapsos con IA (AquaPulse AI)"
)
def endpoint_analizar_acuario(
    data: AquariumDataRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Analiza la telemetría actual de un acuario utilizando el modelo clínico preventivo de Google GenAI (Gemini)
    con Structured Outputs (AnalisisAcuarioSchema).
    Devuelve diagnóstico estructurado de estado, riesgo potencial predictivo y lista de dosis recomendadas.
    """
    try:
        resultado_ia = analizar_parametros_estructurado(data.model_dump())
        return AquariumAnalysisResponse(status="success", analisis=resultado_ia)
    except Exception as e:
        logger.error(f"Error en endpoint_analizar_acuario: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar análisis con IA: {str(e)}"
        )
    """
    Analiza la telemetría actual de un acuario utilizando el modelo clínico preventivo de Google GenAI (Gemini)
    con Structured Outputs (AnalisisAcuarioSchema).
    Devuelve diagnóstico estructurado de estado, riesgo potencial predictivo y lista de dosis recomendadas.
    """
    try:
        resultado_ia = analizar_parametros_estructurado(data.model_dump())
        return AquariumAnalysisResponse(status="success", analisis=resultado_ia)
    except Exception as e:
        logger.error(f"Error en endpoint_analizar_acuario: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al generar análisis con IA: {str(e)}"
        )


# ==============================================================================
# 🧪 TELEMETRÍA Y PARÁMETROS DE COMPATIBILIDAD CON DASHBOARD
# ==============================================================================

@app.get("/api/tanks/{tank_id}/parameters")
def get_tank_parameters(
    tank_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tank = db.query(Tank).filter(Tank.id == tank_id, Tank.user_id == current_user.id).first()
    if not tank:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Acuario no encontrado o no pertenece a tu cuenta."
        )
    from backend.marine_profiles import get_marine_profile
    r_profile = getattr(tank, "reef_profile", None) or getattr(tank, "tank_type", None)
    profile = get_marine_profile(r_profile)
    visible_f = profile.get("visible_fields", {})
    targets = profile.get("targets", {})

    master_params = [
        ("salinity", "Salinidad", "SG", "salinity", True),
        ("temp", "Temperatura", "°C", "temperature", False),
        ("ph", "pH", "pH", "ph", True),
        ("dkh", "Alcalinidad / KH", "dKH", "kh", True),
        ("ca", "Calcio (Ca)", "ppm", "calcium", True),
        ("mg", "Magnesio (Mg)", "ppm", "magnesium", False),
        ("no3", "Nitrato (NO3)", "ppm", "nitrate", True),
        ("po4", "Fosfato (PO4)", "ppm", "phosphate", True),
        ("ammonia", "Amoníaco (NH3)", "ppm", "ammonia", True),
        ("nitrite", "Nitrito (NO2)", "ppm", "nitrite", True),
        ("gh", "Dureza General (GH)", "dGH", "gh_dgh", False),
    ]

    res = []
    for code, name, unit, f_key, is_crit in master_params:
        if visible_f.get(f_key, False):
            t_info = targets.get(f_key, {})
            min_s = float(t_info.get("min", 0.0))
            max_s = float(t_info.get("max", 100.0))
            t_val = float(t_info.get("target", (min_s + max_s) / 2.0))
            res.append({
                "code": code,
                "name": name,
                "unit": unit,
                "optimal_target": t_val,
                "min_safe": min_s,
                "max_safe": max_s,
                "is_critical": is_crit
            })
    return res

@app.get("/api/tanks/{tank_id}/analytics")
def get_tank_analytics(
    tank_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    tank = db.query(Tank).filter(Tank.id == tank_id, Tank.user_id == current_user.id).first()
    if not tank:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Acuario no encontrado o no pertenece a tu cuenta."
        )

    measurements = db.query(Measurement).filter(
        Measurement.user_id == current_user.id,
        Measurement.tank_id == tank.id
    ).order_by(Measurement.timestamp.asc()).all()

    predictions = calculate_predictions(measurements)

    alk = predictions.alkalinity
    ca = predictions.calcium
    wc = predictions.water_change_prediction

    from backend.marine_profiles import get_marine_profile
    r_prof = getattr(tank, "reef_profile", None) or getattr(tank, "tank_type", None)
    profile = get_marine_profile(r_prof)
    visible_f = profile.get("visible_fields", {})
    targets = profile.get("targets", {})

    latest_m = measurements[-1] if measurements else None

    # Mapeo de parámetros para el dashboard calibrado por perfil
    param_meta = [
        ("salinity", "salinity", "Salinidad", "SG", (getattr(latest_m, "salinity_ppt", None) if latest_m else None) or (getattr(latest_m, "salinity", None) if latest_m else None), True, None, None, None),
        ("temp", "temperature", "Temperatura", "°C", (getattr(latest_m, "temperature", None) if latest_m else None) or (getattr(latest_m, "temperatura", None) if latest_m else None), False, None, None, None),
        ("ph", "ph", "pH", "pH", getattr(latest_m, "ph", None) if latest_m else None, True, None, None, None),
        ("dkh", "kh", "Alcalinidad / KH", "dKH", alk.latest_value, True, alk.daily_slope, alk.days_remaining_safe, alk.alert_message),
        ("ca", "calcium", "Calcio (Ca)", "ppm", ca.latest_value, True, ca.daily_slope, ca.days_remaining_safe, ca.alert_message),
        ("mg", "magnesium", "Magnesio (Mg)", "ppm", (getattr(latest_m, "magnesium_ppm", None) if latest_m else None) or (getattr(latest_m, "magnesium", None) if latest_m else None), False, None, None, None),
        ("no3", "nitrate", "Nitrato (NO3)", "ppm", wc.current_nitrate_ppm or (getattr(latest_m, "nitrate_ppm", None) if latest_m else None) or (getattr(latest_m, "nitrate", None) if latest_m else None), True, wc.daily_accumulation_rate, wc.days_until_threshold, wc.message),
        ("po4", "phosphate", "Fosfato (PO4)", "ppm", (getattr(latest_m, "phosphate_ppm", None) if latest_m else None) or (getattr(latest_m, "phosphate", None) if latest_m else None), True, None, None, None),
        ("ammonia", "ammonia", "Amoníaco (NH3)", "ppm", (getattr(latest_m, "ammonia_ppm", None) if latest_m else None) or (getattr(latest_m, "ammonia", None) if latest_m else None), True, None, None, None),
        ("nitrite", "nitrite", "Nitrito (NO2)", "ppm", (getattr(latest_m, "nitrite_ppm", None) if latest_m else None) or (getattr(latest_m, "nitrite", None) if latest_m else None), True, None, None, None),
        ("gh", "gh_dgh", "Dureza General (GH)", "dGH", getattr(latest_m, "gh_dgh", None) if latest_m else None, False, None, None, None),
    ]

    params_list = []
    for p_code, f_key, p_name, p_unit, p_val, is_crit, d_rate, d_thresh, p_msg in param_meta:
        if visible_f.get(f_key, False):
            t_info = targets.get(f_key, {})
            min_s = float(t_info.get("min", 0.0))
            max_s = float(t_info.get("max", 100.0))
            t_val = float(t_info.get("target", (min_s + max_s) / 2.0))

            if p_val is None:
                st = "normal"
            elif p_val < min_s:
                st = "danger_low"
            elif p_val > max_s:
                st = "danger_high"
            else:
                st = "optimal"

            params_list.append({
                "parameter_code": p_code,
                "parameter_name": p_name,
                "unit": p_unit,
                "latest_value": p_val,
                "status": st,
                "target": t_val,
                "min_safe": min_s,
                "max_safe": max_s,
                "daily_rate": d_rate,
                "days_to_threshold": d_thresh,
                "prediction_message": p_msg,
                "is_critical": is_crit
            })

    return {
        "tank_id": tank.id,
        "tank_name": tank.name,
        "tank_type": tank.tank_type,
        "volume_liters": tank.volume_liters,
        "health_score": 88 if alk.status == "safe" else 72,
        "parameters": params_list,
        "alerts": [
            {
                "type": "warning" if "advertencia" in a.lower() or "consumo" in a.lower() else "danger",
                "title": "Alerta de Bioseguridad",
                "message": a,
                "action": "Ajustar dosificación o cambio de agua preventivo."
            }
            for a in predictions.active_alerts
        ],
        "water_change_prediction": {
            "needed": wc.urgency != "safe",
            "days_until": wc.days_until_threshold or 14,
            "suggested_date": wc.suggested_water_change_date or "En 14 días",
            "recommended_percentage": wc.suggested_percentage or 20,
            "recommended_liters": tank.volume_liters * ((wc.suggested_percentage or 20) / 100.0),
            "reason": wc.message
        }
    }


@app.get(
    "/api/marine-profiles",
    summary="Listar todos los perfiles de acuarios (marinos y de agua dulce)"
)
def get_marine_profiles_endpoint():
    """Retorna el catálogo completo de biotipos y perfiles de referencia oficiales de AquaPulse."""
    from backend.marine_profiles import MARINE_PROFILES
    return {
        "status": "success",
        "profiles": list(MARINE_PROFILES.values())
    }


@app.post(
    "/api/diagnostics/feedback",
    response_model=DiagnosticFeedbackResponse,
    summary="Reportar diagnóstico incorrecto con consentimiento para auditoría del modelo"
)
def report_diagnostic_feedback_endpoint(
    payload: DiagnosticFeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Registra el reporte de discrepancia o diagnóstico incorrecto realizado por un usuario (Fase 5).
    Exige consentimiento explícito previo para almacenar el reporte y usarlo en la auditoría del modelo.
    """
    if not payload.consent_given:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Se requiere otorgar consentimiento explícito para remitir el reporte a auditoría."
        )

    if payload.tank_id:
        tank_check = db.query(Tank).filter(Tank.id == payload.tank_id, Tank.user_id == current_user.id).first()
        if not tank_check:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Acuario no encontrado o no pertenece a tu cuenta."
            )

    feedback_record = DiagnosticFeedback(
        user_id=current_user.id,
        tank_id=payload.tank_id,
        diagnosis_summary=payload.diagnosis_summary,
        severity=payload.severity,
        user_comment=payload.user_comment.strip(),
        category=payload.category or "incorrect_diagnosis",
        consent_given=True
    )
    db.add(feedback_record)
    db.commit()
    db.refresh(feedback_record)

    logger.info(f"Feedback de diagnóstico registrado (id={feedback_record.id}, user={current_user.email}): {payload.user_comment[:60]}...")

    return DiagnosticFeedbackResponse(
        status="success",
        message="Reporte recibido correctamente. Gracias por colaborar con la seguridad y precisión de AquaPulse.",
        feedback_id=feedback_record.id,
        consent_given=True
    )


@app.get(
    "/api/tanks/{tank_id}/corrective-actions",
    summary="Obtener recomendaciones de dosificación y acciones correctoras anti-colapso"
)
def get_tank_corrective_actions(
    tank_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Calcula acciones correctoras seguras (Anti-Colapso) para el acuario (Fase 3.3):
    1. Si la corrección necesaria es menor que el error de medición -> no actuar: 'dentro del margen de error, repite la prueba'.
    2. Cambio diario permitido = límite_del_perfil - error.
    3. Extremo que menos corrige: usa el extremo del intervalo que menos corrección exige.
    4. Coordinación química: nunca corregir dos parámetros que interactúan simultáneamente (Mg > KH > Ca).
    5. Retest obligatorio antes de cualquier otra adición.
    """
    tank = db.query(Tank).filter(Tank.id == tank_id, Tank.user_id == current_user.id).first()
    if not tank:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Acuario no encontrado o no pertenece a tu cuenta."
        )

    latest_m = (
        db.query(Measurement)
        .filter(Measurement.tank_id == tank.id, Measurement.user_id == current_user.id)
        .order_by(Measurement.timestamp.desc())
        .first()
    )
    if not latest_m:
        return {
            "tank_id": tank_id,
            "has_measurements": False,
            "message": "No hay mediciones registradas para calcular correcciones.",
            "actions": []
        }

    from backend.marine_profiles import get_marine_profile
    from backend.uncertainty import (
        calculate_measurement_uncertainty,
        calculate_safe_correction,
        coordinate_chemical_corrections
    )

    r_prof = getattr(tank, "reef_profile", None) or getattr(tank, "tank_type", None)
    profile = get_marine_profile(r_prof)
    targets = profile.get("targets", {})

    raw_corrections = {}
    param_map = {
        "kh": latest_m.kh or latest_m.alkalinity_dkh,
        "calcium": latest_m.calcium or latest_m.calcium_ppm,
        "magnesium": latest_m.magnesium or latest_m.magnesium_ppm,
        "salinity": latest_m.salinity or latest_m.salinity_ppt,
        "temperature": latest_m.temperature or latest_m.temperatura,
        "nitrate": latest_m.nitrate or latest_m.nitrate_ppm,
        "phosphate": latest_m.phosphate or latest_m.phosphate_ppm
    }

    daily_delta_limits = {
        "kh": targets.get("kh", {}).get("max_daily_delta") or targets.get("kh", {}).get("warn_daily_delta") or 0.5,
        "calcium": 25.0,
        "magnesium": 50.0,
        "salinity": 1.0,
        "temperature": 1.0,
        "nitrate": 5.0,
        "phosphate": 0.05
    }

    kit_name = getattr(latest_m, "kit", None)
    is_cam = bool(getattr(latest_m, "is_camera_scan", False))

    for p_key, current_val in param_map.items():
        if current_val is not None and p_key in targets:
            t_spec = targets[p_key]
            t_min = t_spec.get("min")
            t_max = t_spec.get("max")
            target_mid = t_spec.get("target") or t_spec.get("ideal") or ((t_min + t_max) / 2.0 if (t_min is not None and t_max is not None) else None)

            if target_mid is not None and (t_min is not None and t_max is not None):
                if current_val < t_min or current_val > t_max:
                    target_goal = t_min if current_val < t_min else t_max
                    u_int = calculate_measurement_uncertainty(p_key, current_val, kit=kit_name, is_camera_scan=is_cam)
                    max_daily = daily_delta_limits.get(p_key, 0.5)

                    action = calculate_safe_correction(
                        parameter=p_key,
                        current_value=float(current_val),
                        target_value=float(target_goal),
                        error=u_int.error,
                        profile_max_daily_change=float(max_daily)
                    )
                    raw_corrections[p_key] = action

    coordinated = coordinate_chemical_corrections(raw_corrections)
    actions_dict = {k: (act.model_dump() if hasattr(act, "model_dump") else act.dict()) for k, act in coordinated.items()}
    actions_list = list(actions_dict.values())
    has_active = any(a.get("can_act", False) for a in actions_list)

    # Resumen metrológico y químico
    paused_count = sum(1 for a in actions_list if a.get("status") == "paused_interaction")
    if paused_count > 0:
        summary_msg = f"Anti-Colapso activo: Hay {paused_count} ajuste(s) pausados por interacción química (Mg > KH > Ca)."
    elif has_active:
        summary_msg = "Ajustes conservadores calculados con margen de error de medición y límites diarios seguros."
    else:
        summary_msg = "Parámetros estables o desviaciones dentro del margen de error del kit."

    return {
        "tank_id": tank.id,
        "tank_name": tank.name,
        "water_type": r_prof,
        "profile": profile["name"],
        "has_measurements": True,
        "measured_at": latest_m.timestamp.isoformat(),
        "actions": actions_dict,
        "actions_list": actions_list,
        "has_active_corrections": has_active,
        "summary": summary_msg
    }


# ==============================================================================
# 🛠️ MÓDULO DE MANTENIMIENTO MECÁNICO Y EQUIPO
# ==============================================================================

@app.get(
    "/api/aquariums/{aquarium_id}/maintenance",
    response_model=List[MaintenanceTaskResponse],
    summary="Listar tareas de mantenimiento del acuario"
)
@app.get(
    "/api/tanks/{aquarium_id}/maintenance",
    response_model=List[MaintenanceTaskResponse],
    include_in_schema=False
)
@app.get(
    "/aquariums/{aquarium_id}/maintenance",
    response_model=List[MaintenanceTaskResponse],
    include_in_schema=False
)
@app.get(
    "/tanks/{aquarium_id}/maintenance",
    response_model=List[MaintenanceTaskResponse],
    include_in_schema=False
)
def get_aquarium_maintenance_tasks(
    aquarium_id: int,
    include_disabled: bool = Query(True, description="Incluir tareas desactivadas"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Devuelve las tareas de mantenimiento activas y calculadas para el acuario."""
    tank = db.query(Tank).filter(Tank.id == aquarium_id, Tank.user_id == current_user.id).first()
    if not tank:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acuario no encontrado o no autorizado.")

    # Auto-sembrado si el acuario aún no tiene tareas
    tasks = db.query(MaintenanceTask).filter(MaintenanceTask.aquarium_id == aquarium_id).all()
    if not tasks:
        tasks = seed_default_maintenance_tasks(db, tank)

    if not include_disabled:
        tasks = [t for t in tasks if t.is_enabled]

    now = datetime.now(timezone.utc)
    res_list = [task_to_response_dict(t, now) for t in tasks]

    def sort_key(item):
        if not item["is_enabled"]:
            return (4, item["days_until_due"] if item["days_until_due"] is not None else 999)
        st = item["status"]
        if st == "overdue":
            return (0, item["days_until_due"] if item["days_until_due"] is not None else -999)
        if st == "due_soon":
            return (1, item["days_until_due"] if item["days_until_due"] is not None else 0)
        if st == "pending":
            return (2, item["frequency_days"])
        return (3, item["days_until_due"] if item["days_until_due"] is not None else 999)

    res_list.sort(key=sort_key)
    return res_list


@app.post(
    "/api/aquariums/{aquarium_id}/maintenance",
    response_model=MaintenanceTaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una tarea de mantenimiento personalizada"
)
@app.post(
    "/api/tanks/{aquarium_id}/maintenance",
    response_model=MaintenanceTaskResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False
)
@app.post(
    "/aquariums/{aquarium_id}/maintenance",
    response_model=MaintenanceTaskResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False
)
@app.post(
    "/tanks/{aquarium_id}/maintenance",
    response_model=MaintenanceTaskResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False
)
def create_maintenance_task(
    aquarium_id: int,
    payload: MaintenanceTaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Permite crear una tarea personalizada de mantenimiento para el acuario."""
    tank = db.query(Tank).filter(Tank.id == aquarium_id, Tank.user_id == current_user.id).first()
    if not tank:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acuario no encontrado o no autorizado.")

    now = datetime.now(timezone.utc)
    new_task = MaintenanceTask(
        aquarium_id=aquarium_id,
        user_id=current_user.id,
        task_key=payload.task_key or "custom",
        title=payload.title.strip(),
        category=payload.category or "mechanical",
        frequency_days=payload.frequency_days,
        last_completed_at=None,
        next_due_at=now + timedelta(days=payload.frequency_days),
        is_enabled=payload.is_enabled,
        notes=payload.notes,
        created_at=now
    )
    db.add(new_task)
    db.commit()
    db.refresh(new_task)
    return task_to_response_dict(new_task, now)


@app.patch(
    "/api/maintenance/{task_id}",
    response_model=MaintenanceTaskResponse,
    summary="Editar una tarea de mantenimiento"
)
@app.patch(
    "/maintenance/{task_id}",
    response_model=MaintenanceTaskResponse,
    include_in_schema=False
)
def update_maintenance_task(
    task_id: int,
    payload: MaintenanceTaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Edita frecuencia, título, estado habilitado o notas de una tarea."""
    task = db.query(MaintenanceTask).filter(MaintenanceTask.id == task_id, MaintenanceTask.user_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarea de mantenimiento no encontrada.")

    now = datetime.now(timezone.utc)
    if payload.title is not None:
        task.title = payload.title.strip()
    if payload.category is not None:
        task.category = payload.category.strip()
    if payload.is_enabled is not None:
        task.is_enabled = payload.is_enabled
    if payload.notes is not None:
        task.notes = payload.notes

    if payload.frequency_days is not None:
        task.frequency_days = payload.frequency_days
        base_time = task.last_completed_at or task.created_at or now
        if base_time.tzinfo is None:
            base_time = base_time.replace(tzinfo=timezone.utc)
        task.next_due_at = base_time + timedelta(days=payload.frequency_days)

    db.commit()
    db.refresh(task)
    return task_to_response_dict(task, now)


@app.post(
    "/api/maintenance/{task_id}/complete",
    response_model=MaintenanceTaskResponse,
    summary="Marcar tarea como completada hoy"
)
@app.post(
    "/maintenance/{task_id}/complete",
    response_model=MaintenanceTaskResponse,
    include_in_schema=False
)
def complete_maintenance_task(
    task_id: int,
    payload: Optional[MaintenanceCompleteRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Registra la finalización de una tarea y recalcula la próxima fecha de vencimiento."""
    task = db.query(MaintenanceTask).filter(MaintenanceTask.id == task_id, MaintenanceTask.user_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarea no encontrada o no autorizada.")

    now = (payload.completed_at if payload and payload.completed_at else None) or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    task.last_completed_at = now
    task.next_due_at = now + timedelta(days=task.frequency_days)

    log_entry = MaintenanceLog(
        task_id=task.id,
        aquarium_id=task.aquarium_id,
        completed_at=now,
        notes=payload.notes if payload else None
    )
    db.add(log_entry)
    db.commit()
    db.refresh(task)

    return task_to_response_dict(task, now)


@app.delete(
    "/api/maintenance/{task_id}",
    summary="Eliminar una tarea de mantenimiento"
)
@app.delete(
    "/maintenance/{task_id}",
    include_in_schema=False
)
def delete_maintenance_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Elimina una tarea de mantenimiento."""
    task = db.query(MaintenanceTask).filter(MaintenanceTask.id == task_id, MaintenanceTask.user_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarea no encontrada o no autorizada.")

    db.delete(task)
    db.commit()
    return {"status": "success", "message": "Tarea de mantenimiento eliminada exitosamente."}


# ==============================================================================
# 💧 REGISTRO Y GESTIÓN DE CAMBIOS DE AGUA
# ==============================================================================

@app.get(
    "/api/tanks/{tank_id}/water-changes",
    response_model=List[WaterChangeResponse],
    summary="Listar historial de cambios de agua"
)
@app.get(
    "/api/aquariums/{tank_id}/water-changes",
    response_model=List[WaterChangeResponse],
    include_in_schema=False
)
@app.get(
    "/tanks/{tank_id}/water-changes",
    response_model=List[WaterChangeResponse],
    include_in_schema=False
)
@app.get(
    "/aquariums/{tank_id}/water-changes",
    response_model=List[WaterChangeResponse],
    include_in_schema=False
)
def get_water_changes(
    tank_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retorna los cambios de agua registrados para el acuario."""
    tank = db.query(Tank).filter(Tank.id == tank_id, Tank.user_id == current_user.id).first()
    if not tank:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acuario no encontrado o no autorizado.")

    logs = (
        db.query(WaterChange)
        .filter(WaterChange.tank_id == tank_id)
        .order_by(WaterChange.performed_at.desc())
        .limit(100)
        .all()
    )
    return [WaterChangeResponse.model_validate(w) for w in logs]


@app.post(
    "/api/tanks/{tank_id}/water-changes",
    response_model=WaterChangeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un cambio de agua con tareas vinculadas opcionales"
)
@app.post(
    "/api/aquariums/{tank_id}/water-changes",
    response_model=WaterChangeResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False
)
@app.post(
    "/tanks/{tank_id}/water-changes",
    response_model=WaterChangeResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False
)
@app.post(
    "/aquariums/{tank_id}/water-changes",
    response_model=WaterChangeResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False
)
def record_water_change(
    tank_id: int,
    payload: WaterChangeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Registra un cambio de agua y, opcionalmente, marca como completadas
    las tareas de mantenimiento seleccionadas (vinculándolas en maintenance_logs).
    """
    tank = db.query(Tank).filter(Tank.id == tank_id, Tank.user_id == current_user.id).first()
    if not tank:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acuario no encontrado o no autorizado.")

    now = payload.performed_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    wc = WaterChange(
        tank_id=tank_id,
        user_id=current_user.id,
        volume_liters=payload.volume_liters,
        percentage=payload.percentage,
        performed_at=now,
        notes=payload.notes,
        created_at=datetime.now(timezone.utc)
    )
    db.add(wc)
    db.commit()
    db.refresh(wc)

    # Si se completaron tareas durante el cambio de agua, marcarlas completadas
    if payload.completed_task_ids:
        for tid in payload.completed_task_ids:
            task = db.query(MaintenanceTask).filter(
                MaintenanceTask.id == tid,
                MaintenanceTask.aquarium_id == tank_id,
                MaintenanceTask.user_id == current_user.id
            ).first()
            if task:
                task.last_completed_at = now
                task.next_due_at = now + timedelta(days=task.frequency_days)
                mlog = MaintenanceLog(
                    task_id=task.id,
                    aquarium_id=tank_id,
                    completed_at=now,
                    linked_water_change_id=wc.id,
                    notes=f"Completada durante cambio de agua ({wc.volume_liters} L)"
                )
                db.add(mlog)
        db.commit()

    return WaterChangeResponse.model_validate(wc)


# ==============================================================================
# 🔔 ENDPOINTS DE WEB PUSH NOTIFICATIONS (VAPID) Y CRON REMINDERS
# ==============================================================================

@app.get(
    "/api/push/vapid-public-key",
    summary="Obtener clave pública VAPID para registro en cliente"
)
def get_vapid_key():
    """Retorna la clave pública VAPID configurada en las variables de entorno."""
    key = get_vapid_public_key()
    return {"public_key": key}


@app.post(
    "/api/push/subscribe",
    response_model=PushSubscriptionResponse,
    status_code=status.HTTP_200_OK,
    summary="Registrar o actualizar suscripción Web Push para el usuario activo"
)
def subscribe_push(
    payload: PushSubscriptionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Registra una suscripción Web Push del navegador vinculada al usuario autenticado.
    Si el endpoint ya existía, actualiza sus credenciales y preferencias.
    """
    sub = db.query(PushSubscription).filter(PushSubscription.endpoint == payload.endpoint).first()
    if sub:
        sub.user_id = current_user.id
        sub.p256dh = payload.p256dh
        sub.auth = payload.auth
        if payload.user_agent is not None:
            sub.user_agent = payload.user_agent
        if payload.notify_maintenance is not None:
            sub.notify_maintenance = payload.notify_maintenance
        if payload.notify_alerts is not None:
            sub.notify_alerts = payload.notify_alerts
    else:
        sub = PushSubscription(
            user_id=current_user.id,
            endpoint=payload.endpoint,
            p256dh=payload.p256dh,
            auth=payload.auth,
            user_agent=payload.user_agent,
            notify_maintenance=payload.notify_maintenance if payload.notify_maintenance is not None else True,
            notify_alerts=payload.notify_alerts if payload.notify_alerts is not None else True
        )
        db.add(sub)

    db.commit()
    db.refresh(sub)
    return sub


@app.post(
    "/api/push/unsubscribe",
    summary="Eliminar suscripción Web Push del usuario"
)
def unsubscribe_push(
    payload: PushUnsubscribeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Elimina la suscripción asociada al endpoint y al usuario activo."""
    sub = db.query(PushSubscription).filter(
        PushSubscription.endpoint == payload.endpoint,
        PushSubscription.user_id == current_user.id
    ).first()
    if sub:
        db.delete(sub)
        db.commit()
        return {"status": "success", "message": "Suscripción eliminada con éxito."}
    return {"status": "not_found", "message": "Suscripción no encontrada."}


@app.patch(
    "/api/push/preferences",
    summary="Actualizar preferencias de alertas para las suscripciones del usuario"
)
def update_push_preferences(
    payload: PushPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Actualiza las preferencias de notificación de mantenimiento y alertas para el usuario."""
    subs = db.query(PushSubscription).filter(PushSubscription.user_id == current_user.id).all()
    for s in subs:
        if payload.notify_maintenance is not None:
            s.notify_maintenance = payload.notify_maintenance
        if payload.notify_alerts is not None:
            s.notify_alerts = payload.notify_alerts
    db.commit()
    return {
        "status": "success",
        "updated_subscriptions": len(subs),
        "notify_maintenance": payload.notify_maintenance,
        "notify_alerts": payload.notify_alerts
    }


@app.post(
    "/api/push/test",
    summary="Enviar notificación push inmediata de prueba"
)
def test_push_notification(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Envía una notificación de prueba en tiempo real al usuario autenticado."""
    sent = send_push_to_user(
        db=db,
        user_id=current_user.id,
        title="🌊 AquaPulse: Notificación de Prueba",
        body="¡Las notificaciones Web Push están funcionando correctamente en tu dispositivo!",
        url="/?tab=dashboard",
        tag="aquapulse-test"
    )
    return {
        "status": "success" if sent > 0 else "no_active_devices",
        "sent_devices": sent,
        "message": f"Se envió la notificación a {sent} dispositivo(s) activo(s)." if sent > 0 else "No se encontraron dispositivos con suscripción activa."
    }


@app.post(
    "/api/cron/send-reminders",
    summary="Ejecutar recordatorios diarios de mantenimiento para tareas vencidas o que vencen hoy"
)
def cron_send_reminders(
    x_cron_secret: Optional[str] = Header(None, alias="X-CRON-SECRET"),
    db: Session = Depends(get_db)
):
    """
    Endpoint seguro invocado por servicio cron diario (ej. GitHub Actions, Render Cron o cron-job.org).
    Requiere encabezado X-CRON-SECRET coincidente con CRON_SECRET del entorno.
    """
    configured_secret = get_cron_secret()
    if not configured_secret or not x_cron_secret or not secrets.compare_digest(x_cron_secret, configured_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autorizado: Encabezado X-CRON-SECRET inválido o ausente."
        )

    summary = process_daily_maintenance_reminders(db)
    return summary


# ==============================================================================
# 🌐 SERVICIO DE LA PWA (SPA FALLBACK)
# ==============================================================================

DIST_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend", "dist"))

if os.path.exists(DIST_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        potential_file = os.path.join(DIST_DIR, full_path)
        if full_path and os.path.isfile(potential_file):
            return FileResponse(potential_file)
        index_file = os.path.join(DIST_DIR, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"status": "AquaPulse API is active"}
