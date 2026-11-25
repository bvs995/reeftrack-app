"""
AquaReef - Módulo Centralizado de Rate Limiting y Cuotas Persistentes (P1.7 / P2.17)
"""
import hmac
import ipaddress
import os
import threading
import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

from fastapi import Request, HTTPException, status
from backend.database import SessionLocal
from backend.models import UserDailyQuota, RateLimitRecord
from backend.services.email_service import mask_email

logger = logging.getLogger("aquapulse.rate_limits")

# ------------------------------------------------------------------------------
# Resolución de la IP real del cliente (P1.7)
#
# Cadena en producción:  navegador -> Vercel (rewrite /api/*) -> balanceador de Render -> uvicorn
#
# Cada proxy AÑADE a la derecha de X-Forwarded-For la IP que se conectó con él; lo que esté a la
# izquierda lo escribió quien hizo la petición y puede ser falso. Por eso nunca se toma la primera
# entrada: se cuentan desde la derecha los saltos que sí son de confianza.
#
#   TRUSTED_PROXY_HOPS   Proxies delante de la app que no se pueden saltar (en Render: 1, su
#                        balanceador; el contenedor no es accesible de otra forma).
#   PROXY_SHARED_SECRET  Secreto que Vercel pone en la cabecera X-Proxy-Secret (transform "set"
#                        de vercel.json, que pisa cualquier valor que mande el visitante). Si la
#                        petición lo trae, se confía en un salto más: el de Vercel. Admite varios
#                        valores separados por comas para rotarlo sin cortes.
#   FORWARDED_ALLOW_IPS  IPs/CIDR de proxies identificables por su IP (por defecto loopback, para
#                        desarrollo con proxy local). OJO: uvicorn también lee esta variable y, si
#                        el par es de confianza, reescribe request.client.host antes de que llegue
#                        aquí; con "*" toma la primera entrada (falsificable). No definirla en Render.
# ------------------------------------------------------------------------------
PROXY_SECRET_HEADER = "X-Proxy-Secret"


def _parse_ip(value: str) -> Optional[ipaddress._BaseAddress]:
    """Interpreta una entrada de X-Forwarded-For ("1.2.3.4", "1.2.3.4:5678", "[::1]:80")."""
    value = (value or "").strip().strip('"')
    if not value:
        return None
    if value.startswith("["):  # IPv6 con puerto
        value = value[1:].split("]", 1)[0]
    elif value.count(":") == 1:  # IPv4 con puerto
        value = value.split(":", 1)[0]
    try:
        return ipaddress.ip_address(value)
    except ValueError:
        return None


def _trusted_networks() -> tuple[bool, list]:
    raw = os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1,::1")
    trust_all = False
    networks = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if item == "*":
            trust_all = True
            continue
        try:
            networks.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            logger.warning("FORWARDED_ALLOW_IPS contiene un valor inválido e ignorado: %r", item)
    return trust_all, networks


def _trusted_proxy_hops() -> int:
    try:
        return max(0, int(os.getenv("TRUSTED_PROXY_HOPS", "0")))
    except ValueError:
        logger.warning("TRUSTED_PROXY_HOPS no es un entero; se usa 0.")
        return 0


def _has_valid_proxy_secret(request: Request) -> bool:
    raw = os.getenv("PROXY_SHARED_SECRET", "")
    secrets_ = [s.strip() for s in raw.split(",") if s.strip()]
    if not secrets_:
        return False
    provided = request.headers.get(PROXY_SECRET_HEADER) or ""
    if not provided:
        return False
    provided_b = provided.encode("utf-8")
    # Comparar contra todos sin cortocircuito para no filtrar cuál coincide por tiempo.
    match = False
    for candidate in secrets_:
        match |= hmac.compare_digest(provided_b, candidate.encode("utf-8"))
    return match


def get_client_ip(request: Request) -> str:
    """
    Resuelve la IP real del cliente sin confiar en cabeceras que el cliente pueda falsificar (P1.7).

    Se arma la cadena X-Forwarded-For + [par TCP] y se recorre desde la derecha descartando:
      1. los primeros N saltos, con N = TRUSTED_PROXY_HOPS (+1 si llega el secreto de Vercel);
      2. después, cualquier salto cuya IP esté en FORWARDED_ALLOW_IPS.
    La primera entrada que no se descarta es el cliente. Si es ilegible se usa el par TCP.
    """
    peer = request.client.host if request.client else "127.0.0.1"

    forwarded = request.headers.get("X-Forwarded-For") or ""
    chain = [part.strip() for part in forwarded.split(",") if part.strip()]
    chain.append(peer)

    hops = _trusted_proxy_hops()
    if hops and _has_valid_proxy_secret(request):
        hops += 1  # el salto de Vercel también es de confianza
    trust_all, networks = _trusted_networks()

    def is_trusted(entry: str) -> bool:
        if trust_all:
            return True
        ip = _parse_ip(entry)
        return ip is not None and any(ip in net for net in networks)

    index = len(chain) - 1
    while index > 0 and (hops > 0 or is_trusted(chain[index])):
        index -= 1
        hops = max(0, hops - 1)

    client_ip = _parse_ip(chain[index])
    if client_ip is None:
        return peer
    return str(client_ip)


if os.getenv("ENVIRONMENT", "").lower() == "production" and "*" in os.getenv("FORWARDED_ALLOW_IPS", ""):
    logger.warning(
        "FORWARDED_ALLOW_IPS='*' en producción: uvicorn y el rate limit tomarán la primera IP de "
        "X-Forwarded-For, que el cliente puede falsificar. Usa TRUSTED_PROXY_HOPS y PROXY_SHARED_SECRET."
    )


AUTH_RATE_LIMIT_IP_MAX = int(os.getenv("AUTH_RATE_LIMIT_IP_MAX", "5"))
AUTH_RATE_LIMIT_EMAIL_MAX = int(os.getenv("AUTH_RATE_LIMIT_EMAIL_MAX", "5"))
AUTH_RATE_LIMIT_WINDOW_SECONDS = float(os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "60.0"))


class PersistentAuthAttemptsAdapter(defaultdict):
    """Adaptador de compatibilidad para auth_attempts que limpia la base de datos en tests."""
    def __init__(self):
        super().__init__(list)

    def clear(self):
        super().clear()
        try:
            db = SessionLocal()
            db.query(RateLimitRecord).filter(RateLimitRecord.action == "auth").delete()
            db.commit()
            db.close()
        except Exception:
            pass


auth_attempts = PersistentAuthAttemptsAdapter()


def check_auth_rate_limit(request: Request, email: Optional[str] = None):
    """
    Aplica rate limit persistente en PostgreSQL/SQLite por IP y por Correo (P1.7).
    Tolerante a múltiples usuarios tras CGNAT / IP móvil mediante ventana deslizante independiente.
    """
    client_ip = get_client_ip(request)
    now_utc = datetime.now(timezone.utc)
    now_ts = now_utc.timestamp()
    window_start = now_ts - AUTH_RATE_LIMIT_WINDOW_SECONDS

    ip_key = f"ip:{client_ip}"
    email_key = f"email:{email.strip().lower()}" if email else None

    db = SessionLocal()
    try:
        # 1. Verificar límite por IP
        ip_count = db.query(RateLimitRecord).filter(
            RateLimitRecord.key == ip_key,
            RateLimitRecord.action == "auth",
            RateLimitRecord.timestamp >= window_start
        ).count()

        if ip_count >= AUTH_RATE_LIMIT_IP_MAX:
            logger.error(f"Límite de intentos de autenticación excedido para IP {client_ip} ({ip_count} intentos). Operación bloqueada.")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Demasiadas solicitudes: Demasiados intentos de acceso desde esta dirección IP. Por favor espera un minuto antes de reintentar.",
                headers={"Retry-After": str(int(AUTH_RATE_LIMIT_WINDOW_SECONDS))}
            )

        # 2. Verificar límite por Correo (anti-fuerza bruta distribuida sobre una misma cuenta)
        if email_key:
            email_count = db.query(RateLimitRecord).filter(
                RateLimitRecord.key == email_key,
                RateLimitRecord.action == "auth",
                RateLimitRecord.timestamp >= window_start
            ).count()

            if email_count >= AUTH_RATE_LIMIT_EMAIL_MAX:
                logger.error(f"Límite de intentos de autenticación excedido para la cuenta {mask_email(email)} ({email_count} intentos). Operación bloqueada.")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Has agotado el límite de intentos permitidos para esta cuenta de correo. Por favor espera un minuto antes de volver a intentarlo.",
                    headers={"Retry-After": str(int(AUTH_RATE_LIMIT_WINDOW_SECONDS))}
                )

        # Registrar intento
        db.add(RateLimitRecord(key=ip_key, action="auth", timestamp=now_ts))
        if email_key:
            db.add(RateLimitRecord(key=email_key, action="auth", timestamp=now_ts))
        db.commit()

        # Limpiar registros viejos periódicamente (> 2 horas)
        purge_limit = now_ts - 7200.0
        db.query(RateLimitRecord).filter(
            RateLimitRecord.action == "auth",
            RateLimitRecord.timestamp < purge_limit
        ).delete(synchronize_session=False)
        db.commit()

    finally:
        db.close()


class UserScanQuotaManager:
    """
    Control de cuotas y rate limiting persistente en PostgreSQL (P1.7 / P2.15).
    Cuota diaria compartida entre escaneos y diagnósticos IA.
    Sobrevive reinicios de workers y se comparte entre múltiples procesos.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._usage = {}

    @classmethod
    def get_daily_limit(cls, subscription_tier: str = "free", is_admin: bool = False, is_premium: bool = False) -> int:
        if is_admin:
            return int(os.environ.get("SCAN_DAILY_LIMIT_ADMIN", "500"))
        if is_premium or subscription_tier == "premium":
            return int(os.environ.get("SCAN_DAILY_LIMIT_PREMIUM", "25"))
        return int(os.environ.get("SCAN_DAILY_LIMIT_FREE", "5"))

    def _get_daily_limit(self, subscription_tier: str, is_admin: bool) -> int:
        return self.get_daily_limit(subscription_tier=subscription_tier, is_admin=is_admin)

    def _get_burst_limit(self, subscription_tier: str, is_admin: bool) -> int:
        if is_admin or subscription_tier == "premium":
            return 15
        return 5

    def get_quota_info(self, user_id: int, subscription_tier: str, is_admin: bool) -> Dict[str, Any]:
        now_utc = datetime.now(timezone.utc)
        today_str = now_utc.strftime("%Y-%m-%d")
        daily_limit = self._get_daily_limit(subscription_tier, is_admin)

        tomorrow_utc = datetime.combine(now_utc.date() + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        reset_seconds = max(1, int((tomorrow_utc - now_utc).total_seconds()))

        db = SessionLocal()
        try:
            record = db.query(UserDailyQuota).filter(
                UserDailyQuota.user_id == user_id,
                UserDailyQuota.date == today_str
            ).first()
            used = record.count if record else 0
        finally:
            db.close()

        remaining = max(0, daily_limit - used)
        return {
            "tier": "admin" if is_admin else subscription_tier,
            "daily_quota": daily_limit,
            "used_today": used,
            "remaining_today": remaining,
            "reset_seconds": reset_seconds
        }

    def check_and_consume(self, user_id: int, subscription_tier: str, is_admin: bool, request: Optional[Request] = None) -> Dict[str, Any]:
        now_utc = datetime.now(timezone.utc)
        now_ts = now_utc.timestamp()
        today_str = now_utc.strftime("%Y-%m-%d")
        daily_limit = self._get_daily_limit(subscription_tier, is_admin)
        burst_limit = self._get_burst_limit(subscription_tier, is_admin)

        tomorrow_utc = datetime.combine(now_utc.date() + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
        reset_seconds = max(1, int((tomorrow_utc - now_utc).total_seconds()))

        db = SessionLocal()
        try:
            # 1. Verificar cuota diaria compartida persistida en BD
            record = db.query(UserDailyQuota).filter(
                UserDailyQuota.user_id == user_id,
                UserDailyQuota.date == today_str
            ).with_for_update().first() if db.bind.dialect.name != "sqlite" else db.query(UserDailyQuota).filter(
                UserDailyQuota.user_id == user_id,
                UserDailyQuota.date == today_str
            ).first()

            current_count = record.count if record else 0
            if current_count >= daily_limit:
                tier_msg = "plan gratuito" if subscription_tier == "free" and not is_admin else "plan actual"
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Has alcanzado tu límite diario de {daily_limit} escaneos y operaciones IA en el {tier_msg}. "
                        f"Tu cuota se reiniciará a las 00:00 UTC ({reset_seconds // 3600}h {(reset_seconds % 3600) // 60}m restantes), "
                        f"o puedes actualizar a Premium para ampliar tu límite."
                    ),
                    headers={
                        "X-RateLimit-Limit": str(daily_limit),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(reset_seconds)
                    }
                )

            # 2. Verificar burst limit por usuario (últimos 60s) en BD
            user_burst_key = f"burst_user:{user_id}"
            user_burst_count = db.query(RateLimitRecord).filter(
                RateLimitRecord.key == user_burst_key,
                RateLimitRecord.action == "ai_burst",
                RateLimitRecord.timestamp >= (now_ts - 60.0)
            ).count()

            if user_burst_count >= burst_limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Demasiadas peticiones de IA en poco tiempo. Por favor espera un minuto antes de reintentar.",
                    headers={
                        "X-RateLimit-Limit": str(daily_limit),
                        "X-RateLimit-Remaining": str(max(0, daily_limit - current_count)),
                        "X-RateLimit-Reset": str(reset_seconds),
                        "Retry-After": "60"
                    }
                )

            # 3. Verificar burst limit por IP (si request está disponible) en BD
            if request:
                client_ip = get_client_ip(request)
                ip_burst_key = f"burst_ip:{client_ip}"
                ip_burst_count = db.query(RateLimitRecord).filter(
                    RateLimitRecord.key == ip_burst_key,
                    RateLimitRecord.action == "ai_burst",
                    RateLimitRecord.timestamp >= (now_ts - 60.0)
                ).count()
                if ip_burst_count >= 30:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Demasiadas peticiones desde tu dirección IP. Por favor espera un minuto.",
                        headers={"Retry-After": "60"}
                    )
                db.add(RateLimitRecord(key=ip_burst_key, action="ai_burst", timestamp=now_ts))

            # 4. Consumir y persistir en BD
            if record:
                record.count += 1
                record.updated_at = datetime.now(timezone.utc)
            else:
                record = UserDailyQuota(user_id=user_id, date=today_str, count=1)
                db.add(record)

            db.add(RateLimitRecord(key=user_burst_key, action="ai_burst", timestamp=now_ts))
            db.commit()

            new_count = current_count + 1
            remaining = max(0, daily_limit - new_count)
            return {
                "tier": "admin" if is_admin else subscription_tier,
                "daily_quota": daily_limit,
                "used_today": new_count,
                "remaining_today": remaining,
                "reset_seconds": reset_seconds
            }
        finally:
            db.close()

    def reset_for_tests(self):
        with self._lock:
            self._usage.clear()
        try:
            db = SessionLocal()
            db.query(UserDailyQuota).delete()
            db.query(RateLimitRecord).delete()
            db.commit()
            db.close()
        except Exception:
            pass


scan_quota_manager = UserScanQuotaManager()
