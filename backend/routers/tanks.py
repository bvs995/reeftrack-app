"""
AquaPulse - Router de Gestión de Acuarios / Tanques (P2.17)
"""
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth import get_current_user
from backend.models import (
    User,
    Tank,
    Measurement,
    TankResponse,
    TankCreate,
    AquariumCreate,
    TankUpdateRequest,
)
from backend.maintenance_service import seed_default_maintenance_tasks
from backend.marine_profiles import get_marine_profile
from backend.analytics import calculate_predictions
from backend.uncertainty import (
    calculate_measurement_uncertainty,
    calculate_safe_correction,
    coordinate_chemical_corrections
)

logger = logging.getLogger("aquapulse.tanks")

router = APIRouter(tags=["Acuarios"])


@router.get(
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


@router.post(
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
    return TankResponse.model_validate(new_tank)


def _create_aquarium_impl(payload: AquariumCreate, current_user: User, db: Session) -> TankResponse:
    new_tank = Tank(
        user_id=current_user.id,
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
    return TankResponse.model_validate(new_tank)


@router.post(
    "/api/aquariums",
    response_model=TankResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo acuario (esquema AquariumCreate)"
)
def create_aquarium_canonical(
    payload: AquariumCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _create_aquarium_impl(payload, current_user, db)


@router.post(
    "/api/acuarios",
    response_model=TankResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False
)
def create_aquarium_es_alias(
    payload: AquariumCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _create_aquarium_impl(payload, current_user, db)


def _update_aquarium_impl(aquarium_id: int, payload: TankUpdateRequest, current_user: User, db: Session):
    tank = db.query(Tank).filter(Tank.id == aquarium_id, Tank.user_id == current_user.id).first()
    if not tank:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Acuario no encontrado o no pertenece a tu cuenta."
        )

    if payload.volume_liters is not None:
        tank.volume_liters = payload.volume_liters
    if payload.name is not None:
        tank.name = payload.name.strip()
    if payload.tank_type is not None:
        tank.tank_type = payload.tank_type.value if hasattr(payload.tank_type, "value") else str(payload.tank_type)
    if payload.reef_profile is not None:
        tank.reef_profile = payload.reef_profile.value if hasattr(payload.reef_profile, "value") else str(payload.reef_profile)
    if payload.dosing_method is not None:
        tank.dosing_method = payload.dosing_method
    if payload.lighting_par is not None:
        tank.lighting_par = payload.lighting_par
    if payload.flow_profile is not None:
        tank.flow_profile = payload.flow_profile
    if payload.notes is not None:
        tank.notes = payload.notes

    db.commit()
    db.refresh(tank)
    return {
        "message": "Acuario actualizado",
        "new_volume": tank.volume_liters,
        "tank_type": tank.tank_type,
        "id": tank.id,
        "name": tank.name,
        "volume_liters": tank.volume_liters,
        "reef_profile": tank.reef_profile,
        "dosing_method": tank.dosing_method,
        "lighting_par": tank.lighting_par,
        "flow_profile": tank.flow_profile,
        "notes": tank.notes
    }


@router.put(
    "/api/aquariums/{aquarium_id}",
    summary="Actualizar parámetros y litraje del acuario"
)
def update_aquarium(
    aquarium_id: int,
    payload: TankUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _update_aquarium_impl(aquarium_id, payload, current_user, db)


@router.put(
    "/api/acuarios/{aquarium_id}",
    include_in_schema=False
)
def update_aquarium_es_alias(
    aquarium_id: int,
    payload: TankUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _update_aquarium_impl(aquarium_id, payload, current_user, db)


@router.put(
    "/api/tanks/{aquarium_id}",
    include_in_schema=False
)
def update_aquarium_tanks_alias(
    aquarium_id: int,
    payload: TankUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _update_aquarium_impl(aquarium_id, payload, current_user, db)


@router.delete(
    "/api/tanks/{tank_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un acuario del usuario"
)
def delete_user_tank(
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

    db.delete(tank)
    db.commit()
    return None


@router.get("/api/tanks/{tank_id}/parameters")
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


@router.get("/api/tanks/{tank_id}/analytics")
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

    r_prof = getattr(tank, "reef_profile", None) or getattr(tank, "tank_type", None)
    profile = get_marine_profile(r_prof)
    visible_f = profile.get("visible_fields", {})
    targets = profile.get("targets", {})

    latest_m = measurements[-1] if measurements else None

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


@router.get(
    "/api/tanks/{tank_id}/corrective-actions",
    summary="Obtener recomendaciones de dosificación y acciones correctoras anti-colapso"
)
def get_tank_corrective_actions(
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
