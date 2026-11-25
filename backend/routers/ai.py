"""
AquaReef - Router de Análisis Clínico Preventivo e Inteligencia Artificial (P2.17)
"""
import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth import get_current_user
from backend.models import (
    User,
    Tank,
    Measurement,
    MaintenanceTask,
    DiagnosticFeedback,
    AquariumDataRequest,
    PredictiveAnalysisJsonResponse,
    AquariumAnalysisResponse,
    DiagnosticFeedbackCreate,
    DiagnosticFeedbackResponse,
)
from backend.rate_limits import scan_quota_manager
from backend.services.ai_service import (
    analizar_parametros_estructurado,
    obtener_tendencia_ultimas_48h
)
from backend.maintenance_service import task_to_response_dict
from backend.ai_validator import generate_rules_deterministic_diagnosis

logger = logging.getLogger("aquapulse.ai")

router = APIRouter(tags=["IA Preventiva"])


@router.post(
    "/api/analisis-predictivo",
    response_model=PredictiveAnalysisJsonResponse,
    summary="Obtener análisis predictivo estructurado en JSON (AquaReef AI)"
)
def obtener_analisis_json(
    data: AquariumDataRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if data.is_draft:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lectura de cámara en estado borrador (sin confirmar): toda lectura por visión es un borrador que el usuario debe confirmar o corregir antes de usarse en un diagnóstico."
        )

    scan_quota_manager.check_and_consume(current_user.id, current_user.subscription_tier, current_user.is_admin, request=request)

    try:
        data_dict = data.model_dump() if hasattr(data, "model_dump") else data.dict()
        target_id = data.acuario_id or data.tank_id
        if target_id:
            tank_obj = db.query(Tank).filter(Tank.id == target_id, Tank.user_id == current_user.id).first()
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
        fallback_res = generate_rules_deterministic_diagnosis(
            aquarium_name=data.nombre_acuario or "Principal",
            biotope=data.tipo or "Acuario",
            rules_alerts=[{"parameter": "diagnóstico", "status": "safe", "severity": "watch", "message": "Diagnóstico de respaldo determinístico por reglas de seguridad."}],
            measured_intervals=[]
        )
        return {"status": "success", "data": fallback_res}


def _get_tendencia_48h_impl(target_id: int, current_user: User, db: Session):
    tank = db.query(Tank).filter(Tank.id == target_id, Tank.user_id == current_user.id).first()
    if not tank:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Acuario no encontrado o no pertenece a tu cuenta."
        )

    resumen = obtener_tendencia_ultimas_48h(db, target_id)
    return {"status": "success", "acuario_id": target_id, "tendencia": resumen}


@router.get(
    "/api/tanks/{tank_id}/tendencia-48h",
    summary="Obtener resumen textual del historial de mediciones de las últimas 48h"
)
def tank_tendencia_48h(
    tank_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _get_tendencia_48h_impl(tank_id, current_user, db)


@router.get(
    "/api/acuarios/{acuario_id}/tendencia-48h",
    summary="Obtener resumen textual del historial de mediciones de las últimas 48h (alias español)",
    include_in_schema=False
)
def acuario_tendencia_48h_alias(
    acuario_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _get_tendencia_48h_impl(acuario_id, current_user, db)


def _analisis_con_historial_impl(target_id: int, request: Request, current_user: User, db: Session):
    scan_quota_manager.check_and_consume(current_user.id, current_user.subscription_tier, current_user.is_admin, request=request)
    tank_obj = db.query(Tank).filter(Tank.id == target_id, Tank.user_id == current_user.id).first()
    if not tank_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Acuario no encontrado o no pertenece a tu cuenta."
        )

    try:
        ultima_medicion = (
            db.query(Measurement)
            .filter(Measurement.tank_id == target_id, Measurement.user_id == current_user.id)
            .order_by(Measurement.timestamp.desc())
            .first()
        )

        if not ultima_medicion:
            raise HTTPException(status_code=404, detail="No se encontraron mediciones para este acuario.")

        tendencia = obtener_tendencia_ultimas_48h(db, target_id)

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

        resultado_ia = analizar_parametros_estructurado(
            datos_para_ia,
            db=db,
            user_id=current_user.id,
            tank_id=target_id
        )

        return {"status": "success", "data": resultado_ia}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint_analisis_con_historial: {e}. Activando fallback determinístico sin error 500.")
        fallback_res = generate_rules_deterministic_diagnosis(
            aquarium_name=getattr(tank_obj, "name", "Principal") if tank_obj else "Principal",
            biotope=getattr(tank_obj, "tank_type", "mixto") if tank_obj else "mixto",
            rules_alerts=[{"parameter": "diagnóstico", "status": "safe", "severity": "watch", "message": "Diagnóstico de respaldo determinístico por reglas de seguridad."}],
            measured_intervals=[]
        )
        return {"status": "success", "data": fallback_res}


@router.post(
    "/api/tanks/{tank_id}/analisis-predictivo",
    response_model=PredictiveAnalysisJsonResponse,
    summary="Análisis predictivo con IA inyectando historial de 48h desde base de datos"
)
def tank_analisis_predictivo(
    tank_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _analisis_con_historial_impl(tank_id, request, current_user, db)


@router.post(
    "/api/acuarios/{acuario_id}/analisis-predictivo",
    response_model=PredictiveAnalysisJsonResponse,
    summary="Análisis predictivo con IA inyectando historial de 48h (alias español)",
    include_in_schema=False
)
def acuario_analisis_predictivo_alias(
    acuario_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _analisis_con_historial_impl(acuario_id, request, current_user, db)


@router.post(
    "/api/tanks/{tank_id}/analisis",
    response_model=PredictiveAnalysisJsonResponse,
    summary="Análisis con IA inyectando historial de 48h (alias legacy)",
    deprecated=True
)
def tank_analisis_legacy_alias(
    tank_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _analisis_con_historial_impl(tank_id, request, current_user, db)


@router.post(
    "/api/acuarios/{acuario_id}/analisis",
    response_model=PredictiveAnalysisJsonResponse,
    summary="Análisis con IA inyectando historial de 48h (alias legacy en español)",
    deprecated=True
)
def acuario_analisis_legacy_alias(
    acuario_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _analisis_con_historial_impl(acuario_id, request, current_user, db)


@router.post(
    "/api/analizar-ia",
    response_model=AquariumAnalysisResponse,
    summary="Analizar parámetros químicos y prever colapsos con IA (AquaReef AI)"
)
def endpoint_analizar_acuario(
    data: AquariumDataRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if data.is_draft:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lectura de cámara en estado borrador (sin confirmar): toda lectura por visión es un borrador que el usuario debe confirmar o corregir antes de usarse en un diagnóstico."
        )

    scan_quota_manager.check_and_consume(current_user.id, current_user.subscription_tier, current_user.is_admin, request=request)

    try:
        data_dict = data.model_dump() if hasattr(data, "model_dump") else data.dict()
        target_id = data.tank_id or data.acuario_id
        resultado_ia = analizar_parametros_estructurado(
            data_dict,
            db=db,
            user_id=current_user.id,
            tank_id=target_id
        )
        return AquariumAnalysisResponse(status="success", analisis=resultado_ia)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error en endpoint_analizar_acuario: {e}. Activando fallback determinístico sin error 500.")
        fallback_res = generate_rules_deterministic_diagnosis(
            aquarium_name=data.nombre_acuario or "Principal",
            biotope=data.tipo or "mixto",
            rules_alerts=[{"parameter": "diagnóstico", "status": "safe", "severity": "watch", "message": "Diagnóstico de respaldo determinístico por reglas de seguridad."}],
            measured_intervals=[]
        )
        return AquariumAnalysisResponse(status="success", analisis=fallback_res)


@router.post(
    "/api/diagnostics/feedback",
    response_model=DiagnosticFeedbackResponse,
    summary="Reportar diagnóstico incorrecto con consentimiento para auditoría del modelo"
)
def report_diagnostic_feedback_endpoint(
    payload: DiagnosticFeedbackCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
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
        message="Reporte recibido correctamente. Gracias por colaborar con la seguridad y precisión de AquaReef.",
        feedback_id=feedback_record.id,
        consent_given=True
    )
