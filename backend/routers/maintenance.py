"""
AquaPulse - Router de Mantenimiento Mecánico y Cambios de Agua (P2.17)
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth import get_current_user
from backend.models import (
    User,
    Tank,
    MaintenanceTask,
    MaintenanceLog,
    WaterChange,
    MaintenanceTaskResponse,
    MaintenanceTaskCreate,
    MaintenanceTaskUpdate,
    MaintenanceCompleteRequest,
    WaterChangeResponse,
    WaterChangeCreate,
)
from backend.maintenance_service import seed_default_maintenance_tasks, task_to_response_dict

logger = logging.getLogger("aquapulse.maintenance")

router = APIRouter(tags=["Mantenimiento"])


def _get_maintenance_tasks_impl(
    aquarium_id: int,
    include_disabled: bool,
    current_user: User,
    db: Session
) -> List[Dict[str, Any]]:
    tank = db.query(Tank).filter(Tank.id == aquarium_id, Tank.user_id == current_user.id).first()
    if not tank:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acuario no encontrado o no autorizado.")

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


@router.get(
    "/api/aquariums/{aquarium_id}/maintenance",
    response_model=List[MaintenanceTaskResponse],
    summary="Listar tareas de mantenimiento del acuario"
)
def get_aquarium_maintenance_tasks(
    aquarium_id: int,
    include_disabled: bool = Query(True, description="Incluir tareas desactivadas"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _get_maintenance_tasks_impl(aquarium_id, include_disabled, current_user, db)


@router.get(
    "/api/tanks/{aquarium_id}/maintenance",
    response_model=List[MaintenanceTaskResponse],
    include_in_schema=False
)
def get_tank_maintenance_tasks_alias(
    aquarium_id: int,
    include_disabled: bool = Query(True, description="Incluir tareas desactivadas"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _get_maintenance_tasks_impl(aquarium_id, include_disabled, current_user, db)


@router.get(
    "/aquariums/{aquarium_id}/maintenance",
    response_model=List[MaintenanceTaskResponse],
    include_in_schema=False
)
def get_aquariums_legacy_alias(
    aquarium_id: int,
    include_disabled: bool = Query(True, description="Incluir tareas desactivadas"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _get_maintenance_tasks_impl(aquarium_id, include_disabled, current_user, db)


@router.get(
    "/tanks/{aquarium_id}/maintenance",
    response_model=List[MaintenanceTaskResponse],
    include_in_schema=False
)
def get_tanks_legacy_alias(
    aquarium_id: int,
    include_disabled: bool = Query(True, description="Incluir tareas desactivadas"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _get_maintenance_tasks_impl(aquarium_id, include_disabled, current_user, db)


def _create_maintenance_task_impl(
    aquarium_id: int,
    payload: MaintenanceTaskCreate,
    current_user: User,
    db: Session
) -> Dict[str, Any]:
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


@router.post(
    "/api/aquariums/{aquarium_id}/maintenance",
    response_model=MaintenanceTaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una tarea de mantenimiento personalizada"
)
def create_maintenance_task(
    aquarium_id: int,
    payload: MaintenanceTaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _create_maintenance_task_impl(aquarium_id, payload, current_user, db)


@router.post(
    "/api/tanks/{aquarium_id}/maintenance",
    response_model=MaintenanceTaskResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False
)
def create_tank_maintenance_task_alias(
    aquarium_id: int,
    payload: MaintenanceTaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _create_maintenance_task_impl(aquarium_id, payload, current_user, db)


@router.post(
    "/aquariums/{aquarium_id}/maintenance",
    response_model=MaintenanceTaskResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False
)
def create_aquariums_legacy_alias(
    aquarium_id: int,
    payload: MaintenanceTaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _create_maintenance_task_impl(aquarium_id, payload, current_user, db)


@router.post(
    "/tanks/{aquarium_id}/maintenance",
    response_model=MaintenanceTaskResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False
)
def create_tanks_legacy_alias(
    aquarium_id: int,
    payload: MaintenanceTaskCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _create_maintenance_task_impl(aquarium_id, payload, current_user, db)


def _update_maintenance_task_impl(
    task_id: int,
    payload: MaintenanceTaskUpdate,
    current_user: User,
    db: Session
) -> Dict[str, Any]:
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


@router.patch(
    "/api/maintenance/{task_id}",
    response_model=MaintenanceTaskResponse,
    summary="Editar una tarea de mantenimiento"
)
def update_maintenance_task(
    task_id: int,
    payload: MaintenanceTaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _update_maintenance_task_impl(task_id, payload, current_user, db)


@router.patch(
    "/maintenance/{task_id}",
    response_model=MaintenanceTaskResponse,
    include_in_schema=False
)
def update_maintenance_task_alias(
    task_id: int,
    payload: MaintenanceTaskUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _update_maintenance_task_impl(task_id, payload, current_user, db)


def _complete_maintenance_task_impl(
    task_id: int,
    payload: Optional[MaintenanceCompleteRequest],
    current_user: User,
    db: Session
) -> Dict[str, Any]:
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


@router.post(
    "/api/maintenance/{task_id}/complete",
    response_model=MaintenanceTaskResponse,
    summary="Marcar tarea como completada hoy"
)
def complete_maintenance_task(
    task_id: int,
    payload: Optional[MaintenanceCompleteRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _complete_maintenance_task_impl(task_id, payload, current_user, db)


@router.post(
    "/maintenance/{task_id}/complete",
    response_model=MaintenanceTaskResponse,
    include_in_schema=False
)
def complete_maintenance_task_alias(
    task_id: int,
    payload: Optional[MaintenanceCompleteRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _complete_maintenance_task_impl(task_id, payload, current_user, db)


def _delete_maintenance_task_impl(task_id: int, current_user: User, db: Session):
    task = db.query(MaintenanceTask).filter(MaintenanceTask.id == task_id, MaintenanceTask.user_id == current_user.id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tarea no encontrada o no autorizada.")

    db.delete(task)
    db.commit()
    return {"status": "success", "message": "Tarea de mantenimiento eliminada exitosamente."}


@router.delete(
    "/api/maintenance/{task_id}",
    summary="Eliminar una tarea de mantenimiento"
)
def delete_maintenance_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _delete_maintenance_task_impl(task_id, current_user, db)


@router.delete(
    "/maintenance/{task_id}",
    include_in_schema=False
)
def delete_maintenance_task_alias(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _delete_maintenance_task_impl(task_id, current_user, db)


def _get_water_changes_impl(tank_id: int, current_user: User, db: Session) -> List[WaterChangeResponse]:
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


@router.get(
    "/api/tanks/{tank_id}/water-changes",
    response_model=List[WaterChangeResponse],
    summary="Listar historial de cambios de agua"
)
def get_water_changes(
    tank_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _get_water_changes_impl(tank_id, current_user, db)


@router.get(
    "/api/aquariums/{tank_id}/water-changes",
    response_model=List[WaterChangeResponse],
    include_in_schema=False
)
def get_aquariums_water_changes_alias(
    tank_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _get_water_changes_impl(tank_id, current_user, db)


@router.get(
    "/tanks/{tank_id}/water-changes",
    response_model=List[WaterChangeResponse],
    include_in_schema=False
)
def get_tanks_water_changes_legacy_alias(
    tank_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _get_water_changes_impl(tank_id, current_user, db)


@router.get(
    "/aquariums/{tank_id}/water-changes",
    response_model=List[WaterChangeResponse],
    include_in_schema=False
)
def get_aquariums_water_changes_legacy_alias(
    tank_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _get_water_changes_impl(tank_id, current_user, db)


def _record_water_change_impl(
    tank_id: int,
    payload: WaterChangeCreate,
    current_user: User,
    db: Session
) -> WaterChangeResponse:
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


@router.post(
    "/api/tanks/{tank_id}/water-changes",
    response_model=WaterChangeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un cambio de agua con tareas vinculadas opcionales"
)
def record_water_change(
    tank_id: int,
    payload: WaterChangeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _record_water_change_impl(tank_id, payload, current_user, db)


@router.post(
    "/api/aquariums/{tank_id}/water-changes",
    response_model=WaterChangeResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False
)
def record_aquariums_water_change_alias(
    tank_id: int,
    payload: WaterChangeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _record_water_change_impl(tank_id, payload, current_user, db)


@router.post(
    "/tanks/{tank_id}/water-changes",
    response_model=WaterChangeResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False
)
def record_tanks_water_change_legacy_alias(
    tank_id: int,
    payload: WaterChangeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _record_water_change_impl(tank_id, payload, current_user, db)


@router.post(
    "/aquariums/{tank_id}/water-changes",
    response_model=WaterChangeResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False
)
def record_aquariums_water_change_legacy_alias(
    tank_id: int,
    payload: WaterChangeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return _record_water_change_impl(tank_id, payload, current_user, db)
