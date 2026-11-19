import os
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from fastapi import FastAPI, APIRouter, Depends, HTTPException, Query, Body, status
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
    MaintenanceTaskCreate,
    MaintenanceTaskUpdate,
    MaintenanceTaskResponse,
    MaintenanceCompleteRequest,
    WaterChangeCreate,
    WaterChangeResponse
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
    create_password_reset_token,
    verify_password_reset_token,
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

app = FastAPI(
    title="AquaPulse Commercial Multi-User API",
    description="Backend SaaS multi-usuario de alta precisión para acuarios con autenticación JWT y aislamiento de datos.",
    version="3.0.0"
)

# Configuración dinámica de CORS para producción (Vercel) y desarrollo local
raw_origins = os.environ.get("ALLOWED_ORIGINS", "*")
if raw_origins == "*":
    origins = ["*"]
    allow_creds = False
else:
    origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
    allow_creds = True

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=allow_creds,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
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

@app.get("/api/health")
def health_check():
    db_ok = check_db_connection()
    return {
        "status": "online" if db_ok else "degraded",
        "database": "connected" if db_ok else "disconnected",
        "service": "AquaPulse Multi-User Predictive Engine",
        "timestamp": datetime.utcnow().isoformat()
    }


# ==============================================================================
# 🔐 ENDPOINTS DE AUTENTICACIÓN Y GESTIÓN DE CUENTAS (JWT)
# ==============================================================================

# Correos con privilegios SuperAdmin automáticos al iniciar sesión o registrarse
AUTO_ADMIN_EMAILS = {
    "paliyo995@gmail.com",
    os.getenv("ADMIN_EMAIL", "").strip().lower()
} - {""}

@app.post(
    "/api/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una nueva cuenta de usuario"
)
def register_user(payload: UserRegister, db: Session = Depends(get_db)):
    """Crea una nueva cuenta de usuario, inicializa su primer acuario y emite token JWT."""
    normalized_email = payload.email.strip().lower()

    existing_user = db.query(User).filter(User.email == normalized_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una cuenta registrada con este correo electrónico."
        )

    # Verificar si el correo tiene asignación automática de administrador
    is_auto_admin = normalized_email in AUTO_ADMIN_EMAILS

    # Crear usuario con plan Gratuito (Freemium)
    new_user = User(
        email=normalized_email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name.strip() if payload.full_name else None,
        unit_preference="liters",
        subscription_tier="premium" if is_auto_admin else "free",
        is_admin=is_auto_admin,
        is_active=True,
        created_at=datetime.utcnow()
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

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

    token = create_access_token({"sub": str(new_user.id), "email": new_user.email})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(new_user)
    )

@app.post(
    "/api/auth/login",
    response_model=TokenResponse,
    summary="Iniciar sesión con correo y contraseña"
)
def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    """Valida credenciales y emite token JWT de sesión. Promueve automáticamente a is_admin si coincide con paliyo995@gmail.com."""
    normalized_email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas. Verifica tu correo y contraseña.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta cuenta ha sido suspendida por un administrador. Contacta a soporte."
        )

    # Auto-promoción a Administrador si coincide con paliyo995@gmail.com o ADMIN_EMAIL
    if normalized_email in AUTO_ADMIN_EMAILS and not user.is_admin:
        user.is_admin = True
        db.commit()
        db.refresh(user)

    token = create_access_token({"sub": str(user.id), "email": user.email})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )

@app.post(
    "/api/auth/forgot-password",
    response_model=PasswordResetResponse,
    summary="Solicitar enlace para restablecer contraseña"
)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Genera un token firmado temporal y emite un enlace de restablecimiento.
    Por seguridad (OWASP), siempre responde de manera neutral para evitar enumeración de correos.
    Si no hay SMTP configurado, imprime el enlace seguro directamente en la consola para pruebas.
    """
    normalized_email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()

    frontend_base = os.getenv("FRONTEND_URL", "").rstrip("/") or "http://localhost:5173"

    if user and user.is_active:
        reset_token = create_password_reset_token(user.email, user.id)
        reset_url = f"{frontend_base}/?reset_token={reset_token}"

        # Salida visual de alta visibilidad en consola para pruebas locales o desarrollo sin SMTP
        print("\n" + "=" * 76, flush=True)
        print("🔑 [AquaPulse Security] ENLACE DE RESTABLECIMIENTO DE CONTRASEÑA GENERADO", flush=True)
        print(f"📧 Destinatario: {user.email} (ID: {user.id})", flush=True)
        print(f"⏱️  Validez: 30 minutos (Token JWT con propósito específico)", flush=True)
        print(f"🔗 Enlace seguro para pruebas locales o sin servidor SMTP:", flush=True)
        print(f"   {reset_url}", flush=True)
        print("=" * 76 + "\n", flush=True)

        return PasswordResetResponse(
            ok=True,
            message="Si tu correo está registrado, recibirás un enlace seguro para restablecer tu contraseña.",
            reset_url_dev=reset_url,
            reset_token_dev=reset_token
        )

    print(f"ℹ️ [AquaPulse Security] Solicitud de restablecimiento para correo no existente o inactivo: {normalized_email}", flush=True)
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
    """Valida el token firmado y actualiza la contraseña con bcrypt exigiendo complejidad estricta."""
    try:
        check_password_complexity(payload.new_password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    token_data = verify_password_reset_token(payload.token)
    user_id = int(token_data["sub"])

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

    # Actualizar hash seguro
    user.hashed_password = hash_password(payload.new_password)
    db.commit()

    print(f"✅ [AquaPulse Security] Contraseña actualizada exitosamente para el usuario: {user.email}", flush=True)

    return PasswordResetResponse(
        ok=True,
        message="Contraseña actualizada exitosamente. Ya puedes iniciar sesión con tu nueva contraseña."
    )

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
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo acuario utilizando el esquema AquariumCreate.
    Valida el biotipo dentro de: arrecife, plantado, dulce, peces_marinos, mixto.
    """
    user_id = current_user.id if current_user else 1
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
    db: Session = Depends(get_db)
):
    """
    Actualiza el volumen en litros de un acuario por su ID.
    Acepta el parámetro volume_liters como query param o en el cuerpo JSON.
    """
    actual_volume = volume_liters
    if actual_volume is None and payload and "volume_liters" in payload:
        actual_volume = payload["volume_liters"]
    elif actual_volume is None and isinstance(payload, int):
        actual_volume = payload

    if actual_volume is None and not (payload and any(k in payload for k in ["name", "tank_type", "type", "notes"])):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Se requiere el campo 'volume_liters' o datos a actualizar")

    tank = db.query(Aquarium).filter(Aquarium.id == aquarium_id).first()
    if not tank:
        tank = db.query(Acuario).filter(Acuario.id == aquarium_id).first()
    if not tank:
        raise HTTPException(status_code=404, detail="Acuario no encontrado")

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
def create_measurement(
    payload: MeasurementCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Guarda una medición vinculada estrictamente al user_id del usuario autenticado.
    Si se especifica tank_id, verifica que pertenezca al usuario.
    """
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
    ca_val = payload.calcium if payload.calcium is not None else payload.calcium_ppm
    mg_val = payload.magnesium if payload.magnesium is not None else payload.magnesium_ppm
    no3_val = payload.nitrate if payload.nitrate is not None else payload.nitrate_ppm
    po4_val = payload.phosphate if payload.phosphate is not None else payload.phosphate_ppm
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
        notes=payload.notes
    )
    db.add(db_measurement)
    db.commit()
    db.refresh(db_measurement)
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Guarda una medición vinculada al acuario especificado por tank_id y al usuario activo.
    """
    payload.tank_id = tank_id
    return create_measurement(payload=payload, current_user=current_user, db=db)

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
    query = db.query(Measurement).filter(Measurement.user_id == current_user.id)
    if tank_id:
        query = query.filter(Measurement.tank_id == tank_id)

    measurements = query.order_by(Measurement.timestamp.asc()).all()
    predictions = calculate_predictions(measurements)
    return predictions


# ==============================================================================
# 📷 ENDPOINT DE VISIÓN ARTIFICIAL (IA VISION)
# ==============================================================================

@app.post(
    "/api/scan-measurement",
    response_model=ScanMeasurementResponse,
    summary="Escanear fotografía de test kit con modelo de visión IA"
)
def scan_measurement_photo(
    payload: ScanMeasurementRequest,
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    """
    Recibe una fotografía en Base64 tomada por el móvil, la procesa mediante
    Google Gemini Vision e identifica el parámetro, valor numérico y test kit.
    """
    try:
        result = analyze_test_image(
            image_data=payload.image_base64,
            preferred_parameter=payload.preferred_parameter,
            allow_demo_fallback=payload.demo_fallback
        )
        return result
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
    db: Session = Depends(get_db)
):
    """
    Endpoint estructurado para obtener diagnóstico predictivo en formato JSON puro.
    Ejecuta inferencia técnica con Gemini mediante esquemas tipados.
    Si se especifica acuario_id o tank_id, consulta automáticamente el historial real de las últimas 48h.
    """
    try:
        data_dict = data.model_dump() if hasattr(data, "model_dump") else data.dict()
        target_id = data.acuario_id or data.tank_id
        if target_id:
            if not data.tendencia_reciente or data.tendencia_reciente in ["Estable en las últimas 24h", "Estable"]:
                historial_48h = obtener_tendencia_ultimas_48h(db, target_id)
                data_dict["tendencia_reciente"] = historial_48h
            tank_obj = db.query(Tank).filter(Tank.id == target_id).first() or db.query(Acuario).filter(Acuario.id == target_id).first()
            if tank_obj:
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

            # Extraer mediciones recientes para evaluación de alertas de delta KH y dosificación
            recent_meas = (
                db.query(Measurement)
                .filter(Measurement.tank_id == target_id)
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
                MaintenanceTask.is_enabled == True
            ).all()
            if active_maint:
                data_dict["maintenance_tasks_summary"] = [
                    task_to_response_dict(t) for t in active_maint
                ]

        resultado_estructurado = analizar_parametros_estructurado(data_dict)
        return {"status": "success", "data": resultado_estructurado}
    except Exception as e:
        logger.error(f"Error en obtener_analisis_json: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
    db: Session = Depends(get_db)
):
    """Consulta las mediciones registradas en las últimas 48h y devuelve la cadena formateada."""
    target_id = tank_id or acuario_id
    if not target_id:
        raise HTTPException(status_code=400, detail="Debe proporcionarse el ID del acuario.")
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
    db: Session = Depends(get_db)
):
    target_id = acuario_id or tank_id
    if not target_id:
        raise HTTPException(status_code=400, detail="Debe especificarse el ID del acuario.")

    try:
        # 1. Obtener la última medición actual del acuario
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
        tank_obj = (
            db.query(Tank).filter(Tank.id == target_id).first()
            or (ultima_medicion.acuario if hasattr(ultima_medicion, "acuario") and ultima_medicion.acuario else None)
            or db.query(Acuario).filter(Acuario.id == target_id).first()
        )
        nombre_acuario = getattr(tank_obj, "nombre", None) or getattr(tank_obj, "name", "Principal") if tank_obj else "Principal"
        volumen_litros = float(getattr(tank_obj, "volumen", None) or getattr(tank_obj, "volume_liters", 280.0) if tank_obj else 280.0)
        tipo_acuario = getattr(tank_obj, "tank_type", None) or getattr(tank_obj, "tipo", "mixto") if tank_obj else "mixto"

        recent_meas = (
            db.query(Measurement)
            .filter(Measurement.tank_id == target_id)
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
                    MaintenanceTask.is_enabled == True
                ).all()
            ]
        }

        # 4. Llamar a tu función de Gemini estructurada
        resultado_ia = analizar_acuario_estructurado(datos_para_ia)

        return {"status": "success", "data": resultado_ia}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint_analisis_con_historial: {e}")
        raise HTTPException(status_code=500, detail=str(e))

app.include_router(router)

@app.post(
    "/api/analizar-ia",
    response_model=AquariumAnalysisResponse,
    summary="Analizar parámetros químicos y prever colapsos con IA (AquaPulse AI)"
)
def endpoint_analizar_acuario(data: AquariumDataRequest):
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
        tank = db.query(Tank).filter(Tank.user_id == current_user.id).first()
        if not tank:
            tank = Tank(user_id=current_user.id, name="Mi Acuario", tank_type="reef", volume_liters=280.0)
            db.add(tank)
            db.commit()
            db.refresh(tank)

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
