"""
AquaPulse - Router de Notificaciones Web Push (VAPID) y Cron Reminders (P2.17)
"""
import secrets
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.auth import get_current_user
from backend.models import (
    User,
    PushSubscription,
    PushSubscriptionCreate,
    PushSubscriptionResponse,
    PushUnsubscribeRequest,
    PushPreferencesUpdate,
)
from backend.push_service import (
    get_vapid_public_key,
    send_push_to_user,
    get_cron_secret,
    process_daily_maintenance_reminders
)

logger = logging.getLogger("aquapulse.push")

router = APIRouter(tags=["Notificaciones Push"])


@router.get(
    "/api/push/vapid-public-key",
    summary="Obtener clave pública VAPID para registro en cliente"
)
def get_vapid_key():
    """Retorna la clave pública VAPID configurada en las variables de entorno."""
    key = get_vapid_public_key()
    return {"public_key": key}


@router.post(
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


@router.post(
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


@router.patch(
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


@router.post(
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


@router.post(
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
