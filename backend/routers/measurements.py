"""
AquaReef - Router de Mediciones y Visión Artificial (P2.17)
"""
import os
import logging
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Response, BackgroundTasks
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth import get_current_user
from backend.models import (
    User,
    Tank,
    Measurement,
    MeasurementCreate,
    MeasurementResponse,
    PredictionResponse,
)
from backend.vision import (
    ScanMeasurementRequest,
    ScanMeasurementResponse,
    analyze_test_image,
)
from backend.rate_limits import scan_quota_manager
from backend.services.ai_service import (
    VISION_AUDIT_STATUS,
    ai_budget_block_reason,
    estimate_gemini_cost,
    record_diagnostic_audit,
)
from backend.analytics import calculate_predictions
from backend.push_service import check_and_notify_measurement_alert

logger = logging.getLogger("aquapulse.measurements")

router = APIRouter(tags=["Mediciones"])


def _create_measurement_impl(
    payload: MeasurementCreate,
    background_tasks: BackgroundTasks,
    current_user: User,
    db: Session
) -> MeasurementResponse:
    # Control de idempotencia (Fase 5 - Cola Offline PWA)
    if payload.client_uuid:
        existing_meas = db.query(Measurement).filter(
            Measurement.client_uuid == payload.client_uuid,
            Measurement.user_id == current_user.id
        ).first()
        if existing_meas:
            logger.info(f"Medición idempotente detectada ({payload.client_uuid}). Retornando existente.")
            return MeasurementResponse.model_validate(existing_meas)

    measurement_time = payload.timestamp or datetime.now(timezone.utc)
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

    try:
        background_tasks.add_task(
            check_and_notify_measurement_alert,
            user_id=current_user.id,
            tank_id=target_tank_id,
            measurement_id=db_measurement.id
        )
    except Exception as bg_err:
        logger.warning(f"Aviso programando tarea push en background: {bg_err}")

    return MeasurementResponse.model_validate(db_measurement)


@router.post(
    "/api/measurements",
    response_model=MeasurementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Guardar una nueva medición vinculada al usuario activo"
)
def create_measurement(
    payload: MeasurementCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _create_measurement_impl(payload, background_tasks, current_user, db)


@router.post(
    "/api/parameter_logs",
    response_model=MeasurementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Guardar una nueva medición (alias parameter_logs)"
)
def create_parameter_logs_alias(
    payload: MeasurementCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _create_measurement_impl(payload, background_tasks, current_user, db)


@router.post(
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
    tank = db.query(Tank).filter(Tank.id == tank_id, Tank.user_id == current_user.id).first()
    if not tank:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Acuario no encontrado o no pertenece a tu cuenta."
        )
    payload.tank_id = tank_id
    return _create_measurement_impl(
        payload=payload,
        background_tasks=background_tasks,
        current_user=current_user,
        db=db
    )


@router.get(
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


@router.get(
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


@router.get(
    "/api/predictions",
    response_model=PredictionResponse,
    summary="Cálculo predictivo sobre los datos del usuario activo"
)
def get_predictions(
    tank_id: Optional[int] = Query(None, description="Filtrar por acuario"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
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


@router.get(
    "/api/scan-quota",
    summary="Consultar cuota restante de escaneos IA del usuario"
)
def get_user_scan_quota(
    current_user: User = Depends(get_current_user)
):
    return scan_quota_manager.get_quota_info(
        user_id=current_user.id,
        subscription_tier=current_user.subscription_tier,
        is_admin=current_user.is_admin
    )


@router.post(
    "/api/scan-measurement",
    response_model=ScanMeasurementResponse,
    summary="Escanear fotografía de test kit con modelo de visión IA"
)
def scan_measurement_photo(
    payload: ScanMeasurementRequest,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Tope de gasto en IA (global y por usuario): si ya se alcanzó, no se llama a Gemini ni se
    # consume cuota; el usuario puede escribir el valor a mano.
    block_reason = ai_budget_block_reason(db, current_user.id)
    if block_reason:
        logger.warning(f"Escaneo bloqueado por presupuesto de IA: {block_reason}")
        return ScanMeasurementResponse(
            success=False,
            api_key_configured=True,
            status="budget_exceeded",
            is_draft=True,
            requires_review=True,
            parameter=payload.preferred_parameter,
            message="El escaneo con IA no está disponible por ahora (se alcanzó el límite de uso de este mes). Ingresa el valor manualmente.",
        )

    quota_info = scan_quota_manager.check_and_consume(
        user_id=current_user.id,
        subscription_tier=current_user.subscription_tier,
        is_admin=current_user.is_admin,
        request=request
    )

    response.headers["X-RateLimit-Limit"] = str(quota_info["daily_quota"])
    response.headers["X-RateLimit-Remaining"] = str(quota_info["remaining_today"])
    response.headers["X-RateLimit-Reset"] = str(quota_info["reset_seconds"])

    try:
        is_dev = os.getenv("ENVIRONMENT", "").strip().lower() == "development"
        usage: dict = {}
        result = analyze_test_image(
            image_data=payload.image_base64,
            preferred_parameter=payload.preferred_parameter,
            allow_demo_fallback=is_dev,
            save_image=payload.save_image,
            usage_sink=usage,
        )
        if usage.get("response") is not None:
            tokens_in, tokens_out, cost_usd = estimate_gemini_cost(usage["response"])
            record_diagnostic_audit(
                db=db,
                user_id=current_user.id,
                tank_id=None,
                prompt_version=f"vision:{usage.get('model', '')}",
                inputs={"parameter": result.parameter, "preferred_parameter": payload.preferred_parameter},
                rules_alerts=[],
                raw_ai_output=None,
                status=VISION_AUDIT_STATUS,
                cost_usd=cost_usd,
                token_count=tokens_in + tokens_out,
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
