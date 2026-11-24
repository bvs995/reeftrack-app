import os
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from pywebpush import webpush, WebPushException

from backend.models import (
    PushSubscription,
    User,
    Tank,
    Measurement,
    MaintenanceTask
)
from backend.maintenance_service import calculate_task_status
from backend.marine_profiles import evaluate_marine_alerts, get_marine_profile

logger = logging.getLogger("aquapulse.push_service")

# Variables de entorno para VAPID y Cron (exclusivamente leídas desde el entorno)
def get_vapid_public_key() -> str:
    return os.environ.get("VAPID_PUBLIC_KEY", "").strip()

def get_vapid_private_key() -> str:
    return os.environ.get("VAPID_PRIVATE_KEY", "").strip()

def get_vapid_claim_email() -> str:
    email = os.environ.get("VAPID_CLAIM_EMAIL", "support@aquapulse.io").strip()
    if email and not email.startswith("mailto:"):
        return f"mailto:{email}"
    return email or "mailto:support@aquapulse.io"

def get_cron_secret() -> str:
    return os.environ.get("CRON_SECRET", "").strip()


def send_push_to_user(
    db: Session,
    user_id: int,
    title: str,
    body: str,
    url: str = "/",
    tag: str = "aquapulse",
    filter_type: Optional[str] = None
) -> int:
    """
    Envía una notificación Web Push a todas las suscripciones activas del usuario indicado.
    Si el servidor push responde con HTTP 404 o 410 (suscripción expirada/desregistrada),
    elimina automáticamente la fila de push_subscriptions.
    Nunca propaga excepciones hacia arriba para no romper flujos principales.
    """
    private_key = get_vapid_private_key()
    claim_email = get_vapid_claim_email()

    if not private_key:
        logger.warning("⚠️ No se ha configurado VAPID_PRIVATE_KEY en el entorno. Notificación omitida.")
        return 0

    query = db.query(PushSubscription).filter(PushSubscription.user_id == user_id)
    if filter_type == "maintenance":
        query = query.filter(PushSubscription.notify_maintenance == True)
    elif filter_type == "alerts":
        query = query.filter(PushSubscription.notify_alerts == True)

    subscriptions = query.all()
    if not subscriptions:
        logger.debug(f"El usuario {user_id} no tiene suscripciones push activas (filtro: {filter_type}).")
        return 0

    payload_data = json.dumps({
        "title": title,
        "body": body,
        "url": url,
        "tag": tag
    })

    claims = {"sub": claim_email}
    sent_count = 0
    subs_to_delete = []

    for sub in subscriptions:
        try:
            sub_info = {
                "endpoint": sub.endpoint,
                "keys": {
                    "p256dh": sub.p256dh,
                    "auth": sub.auth
                }
            }
            webpush(
                subscription_info=sub_info,
                data=payload_data,
                vapid_private_key=private_key,
                vapid_claims=claims,
                timeout=10
            )
            sent_count += 1
            logger.info(f"✅ Push enviado exitosamente a sub id={sub.id} (user={user_id})")
        except WebPushException as ex:
            status_code = ex.response.status_code if ex.response is not None else None
            logger.warning(f"WebPushException al enviar a sub id={sub.id} (status={status_code}): {ex}")
            # Si el endpoint ya no existe o fue revocado por el navegador (404 Not Found o 410 Gone)
            if status_code in [404, 410]:
                subs_to_delete.append(sub)
        except Exception as ex:
            logger.error(f"Error inesperado al enviar WebPush a sub id={sub.id}: {ex}")

    # Limpieza automática de suscripciones obsoletas/revocadas
    if subs_to_delete:
        for obsolete in subs_to_delete:
            try:
                db.delete(obsolete)
            except Exception as del_err:
                logger.error(f"Error borrando sub expirada {obsolete.id}: {del_err}")
        try:
            db.commit()
            logger.info(f"🧹 Se eliminaron {len(subs_to_delete)} suscripciones push expiradas (HTTP 404/410).")
        except Exception as commit_err:
            db.rollback()
            logger.error(f"Error haciendo commit de limpieza de suscripciones: {commit_err}")

    return sent_count


def check_and_notify_measurement_alert(
    user_id: int,
    tank_id: Optional[int],
    measurement_id: int
) -> None:
    """
    Tarea de segundo plano (BackgroundTasks) para evaluar alertas críticas
    y enviar notificaciones push inmediatas si el usuario tiene notify_alerts activado.
    """
    from backend.database import SessionLocal
    db = SessionLocal()
    try:
        meas = db.query(Measurement).filter(Measurement.id == measurement_id).first()
        if not meas:
            return

        tank = None
        if tank_id:
            tank = db.query(Tank).filter(Tank.id == tank_id).first()
        if not tank:
            tank = db.query(Tank).filter(Tank.user_id == user_id).first()

        tank_name = tank.name if tank else "Acuario Principal"
        reef_profile = getattr(tank, "reef_profile", None) if tank else None
        dosing_method = getattr(tank, "dosing_method", None) if tank else None

        # Historial de mediciones para cálculo de delta 24h
        history_measurements = []
        if tank:
            recent = (
                db.query(Measurement)
                .filter(Measurement.tank_id == tank.id, Measurement.id != measurement_id)
                .order_by(Measurement.timestamp.desc())
                .limit(20)
                .all()
            )
            history_measurements = [
                {
                    "timestamp": m.timestamp.isoformat() if hasattr(m.timestamp, "isoformat") else str(m.timestamp),
                    "kh": m.kh or m.alkalinity_dkh,
                    "temperature": m.temperature or m.temperatura,
                    "ph": m.ph,
                    "calcium": m.calcium or m.calcium_ppm,
                    "magnesium": m.magnesium or m.magnesium_ppm,
                    "nitrate": m.nitrate or m.nitrate_ppm,
                    "phosphate": m.phosphate or m.phosphate_ppm,
                    "kit": getattr(m, "kit", None),
                    "is_camera_scan": getattr(m, "is_camera_scan", False)
                }
                for m in recent
            ]

        meas_dict = {
            "timestamp": meas.timestamp.isoformat() if hasattr(meas.timestamp, "isoformat") else str(meas.timestamp),
            "kh": meas.kh or meas.alkalinity_dkh,
            "ph": meas.ph,
            "calcium": meas.calcium or meas.calcium_ppm,
            "magnesium": meas.magnesium or meas.magnesium_ppm,
            "nitrate": meas.nitrate or meas.nitrate_ppm,
            "phosphate": meas.phosphate or meas.phosphate_ppm,
            "salinity": meas.salinity or meas.salinity_ppt,
            "temperature": meas.temperature or meas.temperatura,
            "ammonia": meas.ammonia,
            "nitrite": meas.nitrite,
            "test_methods": meas.test_methods or {},
            "kit": getattr(meas, "kit", None),
            "is_camera_scan": getattr(meas, "is_camera_scan", False)
        }

        # 1. Evaluar alertas dinámicas especializadas (delta KH 24h, nutrientes en cero, etc.)
        marine_alerts = evaluate_marine_alerts(
            reef_profile=reef_profile,
            current_data=meas_dict,
            history_measurements=history_measurements,
            dosing_method=dosing_method
        )

        critical_messages = []

        # Recoger alertas críticas y warnings de marine_alerts
        for ma in marine_alerts:
            sev = ma.get("severity")
            if sev in ["critical", "warning"]:
                critical_messages.append(f"{ma.get('title')}: {ma.get('message', '')}")

        # 2. Reglas toxicológicas directas: Amoníaco (NH3) y Nitrito (NO2)
        if meas.ammonia is not None and float(meas.ammonia) > 0.0:
            critical_messages.append(f"Amoníaco Tóxico: {meas.ammonia} ppm (Peligro letal para peces y corales).")
        if meas.nitrite is not None and float(meas.nitrite) > 0.05:
            critical_messages.append(f"Nitrito Tóxico: {meas.nitrite} ppm (Inhibe el transporte de oxígeno).")

        # 3. Temperatura fuera de rango crítico
        temp = meas.temperature or meas.temperatura
        if temp is not None:
            temp_val = float(temp)
            if temp_val < 23.0:
                critical_messages.append(f"Temperatura Baja Crítica: {temp_val:.1f} °C (Riesgo de shock térmico).")
            elif temp_val > 27.5:
                critical_messages.append(f"Temperatura Alta Crítica: {temp_val:.1f} °C (Riesgo de hipoxia y blanqueamiento).")

        if critical_messages:
            title = f"🚨 Alerta de Calidad: {tank_name}"
            # Resumir el mensaje principal
            body = critical_messages[0]
            if len(critical_messages) > 1:
                body += f" (+{len(critical_messages) - 1} alertas adicionales)"

            send_push_to_user(
                db=db,
                user_id=user_id,
                title=title,
                body=body[:200], # Asegurar longitud óptima para notificación
                url="/?tab=dashboard",
                tag="parameter-alert",
                filter_type="alerts"
            )
    except Exception as e:
        logger.error(f"Error procesando alertas de medición en background: {e}")
    finally:
        db.close()


def process_daily_maintenance_reminders(db: Session) -> Dict[str, Any]:
    """
    Agrupa tareas de mantenimiento activas que están vencidas o vencen hoy
    por usuario con notify_maintenance=True, y envía 1 notificación resumida por usuario.
    """
    # 1. Obtener usuarios que tienen suscripciones push activas con notify_maintenance=True
    active_subs = (
        db.query(PushSubscription)
        .filter(PushSubscription.notify_maintenance == True)
        .all()
    )
    user_ids = list(set([s.user_id for s in active_subs]))
    if not user_ids:
        return {
            "processed_users": 0,
            "sent_notifications": 0,
            "message": "No hay usuarios con suscripciones push de mantenimiento activas."
        }

    sent_total = 0
    details = []

    for uid in user_ids:
        # Obtener todas las tareas habilitadas del usuario
        tasks = (
            db.query(MaintenanceTask)
            .filter(
                MaintenanceTask.user_id == uid,
                MaintenanceTask.is_enabled == True
            )
            .all()
        )

        due_tasks = []
        for t in tasks:
            status = calculate_task_status(t)
            if status in ["due_today", "overdue"]:
                due_tasks.append((t, status))

        if not due_tasks:
            continue

        # Crear mensaje resumido
        overdue_count = sum(1 for _, st in due_tasks if st == "overdue")
        today_count = sum(1 for _, st in due_tasks if st == "due_today")

        task_names = [t.title for t, _ in due_tasks[:3]]
        sample_str = ", ".join(task_names)
        if len(due_tasks) > 3:
            sample_str += f" y {len(due_tasks) - 3} más"

        if overdue_count > 0 and today_count > 0:
            body = f"Tienes {overdue_count} tarea(s) vencidas y {today_count} para hoy ({sample_str})."
        elif overdue_count > 0:
            body = f"Tienes {overdue_count} tarea(s) de mantenimiento vencidas ({sample_str})."
        else:
            body = f"Tienes {today_count} tarea(s) programadas para hoy ({sample_str})."

        title = "🔧 AquaPulse: Mantenimiento Pendiente"
        sent = send_push_to_user(
            db=db,
            user_id=uid,
            title=title,
            body=body,
            url="/?tab=maintenance",
            tag="maintenance-reminder",
            filter_type="maintenance"
        )
        if sent > 0:
            sent_total += sent
            details.append({"user_id": uid, "tasks_count": len(due_tasks), "sent_devices": sent})

    return {
        "processed_users": len(user_ids),
        "sent_notifications": sent_total,
        "details": details
    }
