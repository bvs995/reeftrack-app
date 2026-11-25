"""
Servicio y catálogo oficial de Mantenimiento Mecánico y Equipo para AquaReef.
Genera tareas predeterminadas según el biotipo/perfil del acuario y calcula
el estado de vencimiento con semáforo técnico.
"""
from datetime import datetime, timezone, timedelta
import math
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.models import MaintenanceTask, MaintenanceLog, Tank, MaintenanceTaskResponse


def is_marine_tank(tank: Tank) -> bool:
    """Determina si el acuario es marino o de arrecife."""
    t_type = (getattr(tank, "tank_type", None) or getattr(tank, "tipo", None) or "").lower()
    r_prof = (getattr(tank, "reef_profile", None) or "").lower()
    if r_prof in ["fish_only", "soft_reef", "lps_reef", "mixed_reef", "sps_reef", "fowlr_soft"]:
        return True
    if t_type in ["fish_only", "soft_reef", "lps_reef", "mixed_reef", "sps_reef"]:
        return True
    return any(m in t_type for m in ["reef", "arrecife", "marine", "marino", "mixed", "mixto", "peces_marinos", "fowlr"])


def normalize_reef_profile(tank: Tank) -> str:
    """Devuelve el perfil marino normalizado o 'mixed_reef' por defecto."""
    prof = (getattr(tank, "reef_profile", None) or "").lower()
    t_type = (getattr(tank, "tank_type", None) or "").lower()
    target = prof or t_type
    if target in ["fish_only", "soft_reef", "lps_reef", "mixed_reef", "sps_reef"]:
        return target
    if target in ["fowlr_soft", "fowlr", "solo_peces", "peces_marinos", "marine_fish", "peces"]:
        return "fish_only"
    if target in ["soft", "corales_blandos", "blandos"]:
        return "soft_reef"
    if target in ["lps", "arrecife", "reef"]:
        return "lps_reef"
    if target in ["sps", "acropora", "acroporas"]:
        return "sps_reef"
    if target in ["mixto", "mixed", "arrecife_mixto"]:
        return "mixed_reef"
    return "mixed_reef" if is_marine_tank(tank) else "freshwater"


def get_default_tasks_catalog(tank: Tank) -> List[Dict[str, Any]]:
    """
    Retorna la lista de tareas maestras calibradas para el perfil específico del acuario:
    - fish_only, soft_reef, lps_reef, mixed_reef, sps_reef, plantado, dulce.
    """
    es_marino = is_marine_tank(tank)
    r_prof = normalize_reef_profile(tank)
    t_type = (getattr(tank, "tank_type", None) or getattr(tank, "tipo", None) or "").lower()
    es_plantado = "plant" in t_type

    tasks: List[Dict[str, Any]] = []

    # 1. Limpieza de vidrios / acrílico (Todos los acuarios, 3 días)
    tasks.append({
        "task_key": "glass_cleaning",
        "title": "Limpieza de vidrios / acrílico",
        "category": "mechanical",
        "frequency_days": 3,
        "is_enabled": True,
        "notes": "Limpieza de film bacteriano y microalgas con imán o rasqueta plástica."
    })

    # 2. Esponjas / Calcetines de filtración mecánica (4 días marino, 10 días dulce)
    tasks.append({
        "task_key": "mechanical_filter",
        "title": "Esponjas / Calcetines de filtración",
        "category": "mechanical",
        "frequency_days": 4 if es_marino else 10,
        "is_enabled": True,
        "notes": "Lavar o sustituir perlon, calcetín o esponja para evitar descomposición de detrito en NO3/PO4."
    })

    # 3. Vaciar y lavar copa del Skimmer (Solo marino/arrecife, 5 días)
    if es_marino:
        tasks.append({
            "task_key": "skimmer_cup",
            "title": "Vaciar y lavar copa del Skimmer",
            "category": "mechanical",
            "frequency_days": 5,
            "is_enabled": True,
            "notes": "Remover lodo y limpiar cuello de la copa para maximizar la tensión superficial del espumado."
        })

    # 4. Cambiar carbón activo / resinas GFO (30 días, activo en marino, deshabilitado en dulce)
    tasks.append({
        "task_key": "carbon_gfo",
        "title": "Cambiar carbón activo / resinas GFO" if es_marino else "Renovación de material químico / carbón",
        "category": "chemical",
        "frequency_days": 30,
        "is_enabled": True if es_marino else False,
        "notes": "Sustitución de carbón activado para claridad óptica y/o resinas adsorbentes de fosfatos."
    })

    # 5. Limpieza profunda de bombas recirculadoras y retorno (60 días SPS/Mixto, 90 días los demás)
    pumps_freq = 60 if (es_marino and r_prof in ["sps_reef", "mixed_reef"]) else 90
    pumps_title = "Limpieza profunda de bombas recirculadoras y retorno" if es_marino else "Limpieza de filtro / cabezal"
    tasks.append({
        "task_key": "pumps_cleaning",
        "title": pumps_title,
        "category": "equipment",
        "frequency_days": pumps_freq,
        "is_enabled": True,
        "notes": "Desmontar y desincrustar propela e imanes con baño de vinagre o ácido cítrico para restaurar flujo."
    })

    # 6. Limpieza profunda de cuerpo y propela del Skimmer (90 días, solo marinos)
    if es_marino:
        tasks.append({
            "task_key": "skimmer_body",
            "title": "Limpieza profunda de cuerpo y propela del Skimmer",
            "category": "equipment",
            "frequency_days": 90,
            "is_enabled": True,
            "notes": "Descalcificar bomba de inyección venturi y difusor de burbujas."
        })

    # 7. Revisión y calibración de dosificadoras / sondas (45 días en LPS/Mixto/SPS, CO2 en plantado, oculto en fish_only)
    if es_marino and r_prof in ["lps_reef", "mixed_reef", "sps_reef"]:
        tasks.append({
            "task_key": "doser_probes",
            "title": "Revisión y calibración de dosificadoras / sondas",
            "category": "calibration",
            "frequency_days": 45,
            "is_enabled": True,
            "notes": "Verificar precisión milimétrica de cabezales peristálticos (Balling) y calibrar electrodos de pH."
        })
    elif es_plantado:
        tasks.append({
            "task_key": "doser_probes",
            "title": "Revisión de CO₂ y difusor",
            "category": "calibration",
            "frequency_days": 45,
            "is_enabled": False,
            "notes": "Revisar cuentagotas, válvula solenoide y limpiar micro-difusor cerámico de CO2."
        })

    return tasks


def seed_default_maintenance_tasks(db: Session, tank: Tank) -> List[MaintenanceTask]:
    """
    Inserta las tareas predeterminadas correspondientes al acuario si aún no tiene tareas.
    Retorna la lista de tareas creadas o existentes.
    """
    existing = db.query(MaintenanceTask).filter(MaintenanceTask.aquarium_id == tank.id).all()
    if existing:
        return existing

    catalog = get_default_tasks_catalog(tank)
    now = datetime.now(timezone.utc)
    created_tasks: List[MaintenanceTask] = []

    for item in catalog:
        freq = item["frequency_days"]
        task = MaintenanceTask(
            aquarium_id=tank.id,
            user_id=tank.user_id,
            task_key=item.get("task_key"),
            title=item["title"],
            category=item.get("category", "mechanical"),
            frequency_days=freq,
            last_completed_at=None,
            next_due_at=now + timedelta(days=freq),
            is_enabled=item.get("is_enabled", True),
            notes=item.get("notes"),
            created_at=now
        )
        db.add(task)
        created_tasks.append(task)

    db.commit()
    for t in created_tasks:
        db.refresh(t)

    return created_tasks


def calculate_task_status(task: MaintenanceTask, now: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Calcula dinámicamente days_since_last, days_until_due y status:
    - 'overdue'  : Si next_due_at ya pasó (diferencia < 0)
    - 'due_soon' : Si falta 1 día o menos
    - 'ok'       : Si faltan > 1 día
    - 'pending'  : Si nunca se ha completado
    """
    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # Normalizar next_due_at
    next_due = task.next_due_at
    if next_due is not None and next_due.tzinfo is None:
        next_due = next_due.replace(tzinfo=timezone.utc)

    # Normalizar last_completed_at
    last_comp = task.last_completed_at
    if last_comp is not None and last_comp.tzinfo is None:
        last_comp = last_comp.replace(tzinfo=timezone.utc)

    days_since_last: Optional[int] = None
    if last_comp is not None:
        days_since_last = max(0, int((now - last_comp).total_seconds() // 86400))

    if next_due is None:
        if last_comp is not None:
            next_due = last_comp + timedelta(days=task.frequency_days)
        else:
            next_due = now + timedelta(days=task.frequency_days)

    diff_seconds = (next_due - now).total_seconds()
    days_until_due = math.ceil(diff_seconds / 86400)

    if diff_seconds < 0:
        status = "overdue"
    elif diff_seconds <= 86400: # <= 1 día
        status = "due_soon"
    elif last_comp is None:
        status = "pending"
    else:
        status = "ok"

    return {
        "days_since_last": days_since_last,
        "days_until_due": days_until_due,
        "status": status,
        "next_due_at": next_due
    }


def task_to_response_dict(task: MaintenanceTask, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Convierte un modelo MaintenanceTask a un diccionario con campos calculados."""
    st = calculate_task_status(task, now)
    return {
        "id": task.id,
        "aquarium_id": task.aquarium_id,
        "user_id": task.user_id,
        "task_key": task.task_key,
        "title": task.title,
        "category": task.category,
        "frequency_days": task.frequency_days,
        "last_completed_at": task.last_completed_at,
        "next_due_at": st["next_due_at"],
        "is_enabled": task.is_enabled,
        "notes": task.notes,
        "created_at": task.created_at,
        "days_since_last": st["days_since_last"],
        "days_until_due": st["days_until_due"],
        "status": st["status"]
    }
