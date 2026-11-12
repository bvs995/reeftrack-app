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
    Measurement,
    MeasurementCreate,
    MeasurementResponse,
    PredictionResponse
)
from backend.analytics import calculate_predictions
from backend.seed import seed_database_if_empty
from backend.vision import (
    ScanMeasurementRequest,
    ScanMeasurementResponse,
    analyze_test_image
)

app = FastAPI(
    title="AquaPulse API",
    description="Backend de alta precisión para acuarios con motor de predicción de consumo bioquímico.",
    version="2.0.0"
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
        "service": "AquaPulse Biochemical Predictive Engine",
        "timestamp": datetime.utcnow().isoformat()
    }

# ----------------- ENDPOINTS REQUERIDOS -----------------

@app.post(
    "/api/measurements",
    response_model=MeasurementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Guardar una nueva medición de agua"
)
def create_measurement(
    payload: MeasurementCreate,
    db: Session = Depends(get_db)
):
    """
    Guarda una nueva medición en la base de datos SQLite con SQLAlchemy:
    - alkalinity_dkh
    - calcium_ppm
    - magnesium_ppm
    - nitrate_ppm
    - phosphate_ppm
    - salinity_ppt
    - notes
    - timestamp (si se omite, se usa datetime.utcnow())
    """
    measurement_time = payload.timestamp or datetime.utcnow()
    
    db_measurement = Measurement(
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

@app.post(
    "/api/scan-measurement",
    response_model=ScanMeasurementResponse,
    summary="Escanear fotografía de test kit con modelo de visión IA"
)
def scan_measurement_photo(payload: ScanMeasurementRequest):
    """
    Recibe una fotografía en Base64 tomada por el móvil, la procesa mediante
    un modelo de visión multimodal (Google Gemini Vision) e identifica
    el parámetro medido, el valor numérico, el test kit y la certidumbre.
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

@app.get(
    "/api/measurements",
    response_model=List[MeasurementResponse],
    summary="Obtener historial de mediciones"
)
def get_measurements(
    limit: int = Query(100, ge=1, le=500, description="Número máximo de registros"),
    order: str = Query("desc", pattern="^(asc|desc)$", description="Orden cronológico"),
    db: Session = Depends(get_db)
):
    """
    Retorna el historial completo de mediciones ordenado por fecha.
    """
    query = db.query(Measurement)
    if order == "asc":
        query = query.order_by(Measurement.timestamp.asc())
    else:
        query = query.order_by(Measurement.timestamp.desc())
    
    return query.limit(limit).all()

@app.get(
    "/api/predictions",
    response_model=PredictionResponse,
    summary="Cálculo de consumo y alertas predictivas"
)
def get_predictions(
    db: Session = Depends(get_db)
):
    """
    Ejecuta el motor de análisis predictivo sobre las lecturas registradas:
    - Tasa de consumo diario (regresión lineal sobre las últimas 3 a 5 lecturas para dKH y Calcio).
    - Días restantes antes de salir del rango seguro (rango dKH seguro: 7.5 - 9.0 dKH).
    - Predicción de acumulación de nitratos y fecha estimada para sugerir cambio de agua (límite 20 ppm).
    - Nivel de confianza estadística: indica si se necesitan más datos si hay menos de 3 mediciones en los últimos 14 días.
    """
    measurements = db.query(Measurement).order_by(Measurement.timestamp.asc()).all()
    predictions = calculate_predictions(measurements)
    return predictions

# ----------------- COMPATIBILIDAD CON DASHBOARD PWA -----------------

@app.get("/api/tanks")
def get_tanks():
    return [
        {
            "id": 1,
            "name": "Arrecife Mixto SPS/LPS",
            "tank_type": "reef",
            "volume_liters": 280.0,
            "created_at": "2026-11-01T00:00:00",
            "notes": "Tanque principal de prueba"
        }
    ]

@app.get("/api/tanks/{tank_id}/parameters")
def get_tank_parameters(tank_id: int):
    return [
        {"code": "dkh", "name": "Alcalinidad / KH", "unit": "dKH", "optimal_target": 8.3, "min_safe": 7.5, "max_safe": 9.0, "is_critical": True},
        {"code": "ca", "name": "Calcio (Ca)", "unit": "ppm", "optimal_target": 420.0, "min_safe": 400.0, "max_safe": 450.0, "is_critical": True},
        {"code": "mg", "name": "Magnesio (Mg)", "unit": "ppm", "optimal_target": 1350.0, "min_safe": 1280.0, "max_safe": 1420.0, "is_critical": False},
        {"code": "no3", "name": "Nitrato (NO3)", "unit": "ppm", "optimal_target": 5.0, "min_safe": 2.0, "max_safe": 20.0, "is_critical": True},
        {"code": "po4", "name": "Fosfato (PO4)", "unit": "ppm", "optimal_target": 0.04, "min_safe": 0.02, "max_safe": 0.08, "is_critical": True},
        {"code": "salinity", "name": "Salinidad", "unit": "SG", "optimal_target": 1.025, "min_safe": 1.024, "max_safe": 1.026, "is_critical": True}
    ]

@app.get("/api/tanks/{tank_id}/analytics")
def get_tank_analytics(tank_id: int, db: Session = Depends(get_db)):
    measurements = db.query(Measurement).order_by(Measurement.timestamp.asc()).all()
    predictions = calculate_predictions(measurements)
    
    # Adaptar formato de respuesta para el dashboard
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
        "tank_id": 1,
        "tank_name": "Arrecife Mixto SPS/LPS",
        "tank_type": "reef",
        "volume_liters": 280.0,
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
            "recommended_liters": 280.0 * ((wc.suggested_percentage or 20) / 100.0),
            "reason": wc.message
        }
    }


# ----------------- SERVICIO DE LA PWA (SPA FALLBACK) -----------------

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
