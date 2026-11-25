"""
AquaPulse - Router de Administración del Sistema (P2.17)
"""
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth import get_current_user, get_current_admin_user
from backend.models import (
    User,
    Tank,
    Measurement,
    AdminUserListItem,
    AdminUserUpdate,
    DiagnosticAuditStatsResponse,
)

logger = logging.getLogger("aquapulse.admin")

router = APIRouter(tags=["Administración"])


@router.get(
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


@router.put(
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


@router.delete(
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


@router.get(
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
