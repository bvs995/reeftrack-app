import os
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend.database import get_db, init_db, check_db_connection
from backend.models import (
    User,
    Tank,
    Measurement,
    UserRegister,
    UserLogin,
    UserUpdate,
    UserResponse,
    TokenResponse,
    TankCreate,
    TankResponse,
    MeasurementCreate,
    MeasurementResponse,
    PredictionResponse
)
from backend.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_optional_current_user
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

@app.on_event("startup")
def startup_event():
    # Inicializa las tablas de SQLAlchemy y agrega datos iniciales si está vacía
    init_db()
    db = next(get_db())
    try:
        seed_database_if_empty(db)
    finally:
        db.close()

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

    # Crear usuario con plan Gratuito (Freemium)
    new_user = User(
        email=normalized_email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name.strip() if payload.full_name else None,
        unit_preference="liters",
        subscription_tier="free",
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
    """Valida credenciales y emite token JWT de sesión."""
    normalized_email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas. Verifica tu correo y contraseña.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = create_access_token({"sub": str(user.id), "email": user.email})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
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
        notes=payload.notes
    )
    db.add(new_tank)
    db.commit()
    db.refresh(new_tank)
    return TankResponse.model_validate(new_tank)

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
        target_tank_id = user_tank.id if user_tank else None

    db_measurement = Measurement(
        user_id=current_user.id,
        tank_id=target_tank_id,
        timestamp=measurement_time,
        alkalinity_dkh=payload.alkalinity_dkh,
        calcium_ppm=payload.calcium_ppm,
        magnesium_ppm=payload.magnesium_ppm,
        nitrate_ppm=payload.nitrate_ppm,
        phosphate_ppm=payload.phosphate_ppm,
        salinity_ppt=payload.salinity_ppt,
        notes=payload.notes
    )
    db.add(db_measurement)
    db.commit()
    db.refresh(db_measurement)
    return db_measurement

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
# 🧪 TELEMETRÍA Y PARÁMETROS DE COMPATIBILIDAD CON DASHBOARD
# ==============================================================================

@app.get("/api/tanks/{tank_id}/parameters")
def get_tank_parameters(
    tank_id: int,
    current_user: User = Depends(get_current_user)
):
    return [
        {"code": "dkh", "name": "Alcalinidad / KH", "unit": "dKH", "optimal_target": 8.3, "min_safe": 7.5, "max_safe": 9.0, "is_critical": True},
        {"code": "ca", "name": "Calcio (Ca)", "unit": "ppm", "optimal_target": 420.0, "min_safe": 400.0, "max_safe": 450.0, "is_critical": True},
        {"code": "mg", "name": "Magnesio (Mg)", "unit": "ppm", "optimal_target": 1350.0, "min_safe": 1280.0, "max_safe": 1420.0, "is_critical": False},
        {"code": "no3", "name": "Nitrato (NO3)", "unit": "ppm", "optimal_target": 5.0, "min_safe": 2.0, "max_safe": 20.0, "is_critical": True},
        {"code": "po4", "name": "Fosfato (PO4)", "unit": "ppm", "optimal_target": 0.04, "min_safe": 0.02, "max_safe": 0.08, "is_critical": True},
        {"code": "salinity", "name": "Salinidad", "unit": "SG", "optimal_target": 1.025, "min_safe": 1.024, "max_safe": 1.026, "is_critical": True}
    ]

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

    params_list = [
        {
            "parameter_code": "dkh",
            "parameter_name": "Alcalinidad / KH",
            "unit": "dKH",
            "latest_value": alk.latest_value,
            "status": "optimal" if alk.status == "safe" else "danger_low" if "below" in alk.status else "danger_high" if "above" in alk.status else "normal",
            "target": 8.3,
            "min_safe": 7.5,
            "max_safe": 9.0,
            "daily_rate": alk.daily_slope,
            "days_to_threshold": alk.days_remaining_safe,
            "prediction_message": alk.alert_message,
            "is_critical": True
        },
        {
            "parameter_code": "ca",
            "parameter_name": "Calcio (Ca)",
            "unit": "ppm",
            "latest_value": ca.latest_value,
            "status": "optimal" if ca.status == "safe" else "normal",
            "target": 420.0,
            "min_safe": 400.0,
            "max_safe": 450.0,
            "daily_rate": ca.daily_slope,
            "days_to_threshold": ca.days_remaining_safe,
            "prediction_message": ca.alert_message,
            "is_critical": True
        },
        {
            "parameter_code": "no3",
            "parameter_name": "Nitrato (NO3)",
            "unit": "ppm",
            "latest_value": wc.current_nitrate_ppm,
            "status": "optimal" if (wc.current_nitrate_ppm or 0) < 15 else "danger_high",
            "target": 5.0,
            "min_safe": 2.0,
            "max_safe": 20.0,
            "daily_rate": wc.daily_accumulation_rate,
            "days_to_threshold": wc.days_until_threshold,
            "prediction_message": wc.message,
            "is_critical": True
        }
    ]

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
