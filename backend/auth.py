import os
import logging
import secrets
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from backend.database import get_db
from backend.models import User

load_dotenv()
logger = logging.getLogger("aquapulse.auth")

# 1. Validación estricta de SECRET_KEY: falla el arranque si falta o está vacía
RAW_SECRET = os.environ.get("SECRET_KEY") or os.environ.get("JWT_SECRET")
if not RAW_SECRET or not RAW_SECRET.strip():
    critical_msg = (
        "🚨 ERROR CRÍTICO DE SEGURIDAD: La variable de entorno SECRET_KEY no está configurada o está vacía.\n"
        "AquaPulse se niega a arrancar sin una clave secreta configurada explícitamente en el entorno.\n"
        "Configura SECRET_KEY en tu archivo .env o en el panel de variables de entorno de tu servidor."
    )
    logger.critical(critical_msg)
    raise RuntimeError(critical_msg)

JWT_SECRET = RAW_SECRET.strip()
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # JWT de vida corta (15 min) según especificación FASE 1
REFRESH_TOKEN_EXPIRE_DAYS = 7     # Refresh token rotativo de 7 días

security = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    """Genera hash seguro de contraseña usando bcrypt con factor de coste >= 12."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si la contraseña en texto plano coincide con el hash almacenado."""
    try:
        if not plain_password or not hashed_password:
            return False
        plain_bytes = plain_password.encode("utf-8") if isinstance(plain_password, str) else plain_password
        hash_bytes = hashed_password.encode("utf-8") if isinstance(hashed_password, str) else hashed_password
        return bcrypt.checkpw(plain_bytes, hash_bytes)
    except Exception as e:
        logger.warning(f"Error verificando contraseña: {e}")
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Genera un token JWT firmado de vida corta (15 min) para autenticación de API."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "purpose": "access"})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_refresh_token(user_id: int, expires_delta: Optional[timedelta] = None) -> str:
    """Genera un refresh token rotativo criptográficamente aleatorio (7 días)."""
    expire = datetime.utcnow() + (expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    payload = {
        "sub": str(user_id),
        "purpose": "refresh",
        "jti": secrets.token_hex(16),
        "exp": expire,
        "iat": datetime.utcnow()
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_refresh_token(token: str) -> dict:
    """Valida un refresh token y asegura que tenga purpose='refresh'."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="La sesión de refresco ha expirado. Por favor inicia sesión nuevamente."
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de refresco inválido o corrupto."
        )

    if payload.get("purpose") != "refresh" or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token proporcionado no es un token de refresco válido."
        )

    return payload

def create_password_reset_token(email: str, user_id: int, expires_delta: Optional[timedelta] = None) -> Tuple[str, str, datetime]:
    """
    Genera un token criptográfico firmado temporal (30 min) para restablecimiento de contraseña.
    Retorna (token_jwt, jti, expire_datetime).
    """
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=30))
    jti = secrets.token_hex(16)
    payload = {
        "sub": str(user_id),
        "email": email.strip().lower(),
        "purpose": "password_reset",
        "jti": jti,
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, jti, expire

def verify_password_reset_token(token: str) -> dict:
    """Valida estrictamente la firma, expiración y estructura de un token de restablecimiento de contraseña."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de restablecimiento ha expirado. Por favor solicita uno nuevo."
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de restablecimiento es inválido o está corrupto."
        )

    if payload.get("purpose") != "password_reset" or "sub" not in payload or "jti" not in payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El token proporcionado no es válido para restablecimiento de contraseña."
        )

    return payload

def send_password_reset_email(to_email: str, reset_url: str) -> bool:
    """
    Envía enlace seguro de reseteo mediante SMTP transaccional configurado por variables de entorno.
    Si no hay SMTP configurado, no expone el token ni la URL en logs (cumplimiento auditoría P0).
    """
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", "noreply@aquapulse.io")
    smtp_tls = os.getenv("SMTP_TLS", "true").lower() in ("true", "1", "yes")

    if not smtp_host:
        logger.info(f"Proveedor SMTP no configurado; notificación procesada de forma segura para usuario registrado.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "AquaPulse - Restablecimiento de contraseña"
        msg["From"] = smtp_from
        msg["To"] = to_email

        text_content = (
            f"Hola,\n\n"
            f"Hemos recibido una solicitud para restablecer la contraseña de tu cuenta en AquaPulse.\n"
            f"Por favor ingresa al siguiente enlace seguro para actualizar tu contraseña:\n"
            f"{reset_url}\n\n"
            f"Este enlace es de un solo uso y expirará en 30 minutos.\n"
            f"Si tú no realizaste esta solicitud, puedes ignorar este mensaje.\n\n"
            f"— El equipo de AquaPulse"
        )
        msg.attach(MIMEText(text_content, "plain"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            if smtp_tls:
                server.starttls()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, [to_email], msg.as_string())
        return True
    except Exception as e:
        logger.error(f"Error enviando correo transaccional de reseteo: {type(e).__name__}")
        return False

def create_email_verification_token(email: str, user_id: int, expires_delta: Optional[timedelta] = None) -> str:
    """Genera token JWT firmado (24h) para verificación de correo electrónico."""
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(hours=24))
    payload = {
        "sub": str(user_id),
        "email": email.strip().lower(),
        "purpose": "email_verification",
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_email_verification_token(token: str) -> dict:
    """Valida un token de verificación de correo electrónico."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de verificación ha expirado. Por favor solicita uno nuevo."
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El token de verificación es inválido o está corrupto."
        )

    if payload.get("purpose") != "email_verification" or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El token proporcionado no es válido para verificación de correo."
        )

    return payload

def send_email_verification(to_email: str, verify_url: str) -> bool:
    """Envía correo transaccional de verificación mediante SMTP si está configurado."""
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", "noreply@aquapulse.io")
    smtp_tls = os.getenv("SMTP_TLS", "true").lower() in ("true", "1", "yes")

    if not smtp_host:
        logger.info("Proveedor SMTP no configurado; notificación de verificación registrada de forma segura.")
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "AquaPulse - Verifica tu correo electrónico"
        msg["From"] = smtp_from
        msg["To"] = to_email
        text_content = (
            f"Hola,\n\n"
            f"Gracias por registrarte en AquaPulse. Para activar tu cuenta, por favor verifica tu correo:\n"
            f"{verify_url}\n\n"
            f"Este enlace expirará en 24 horas.\n\n"
            f"— El equipo de AquaPulse"
        )
        msg.attach(MIMEText(text_content, "plain"))
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            if smtp_tls:
                server.starttls()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, [to_email], msg.as_string())
        return True
    except Exception as e:
        logger.error(f"Error enviando correo de verificación: {type(e).__name__}")
        return False

def decode_access_token(token: str) -> Optional[dict]:
    """Decodifica y valida la firma y expiración de un token JWT."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        logger.warning("Token JWT expirado")
        return None
    except jwt.PyJWTError as e:
        logger.warning(f"Token JWT inválido: {e}")
        return None

def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Dependencia estricta de autenticación:
    Exige la cabecera 'Authorization: Bearer <token>', valida la firma y recupera el usuario activo.
    """
    if not auth or not auth.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación requerida. Por favor inicia sesión.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = decode_access_token(auth.credentials)
    if not payload or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión expirada o token inválido. Inicia sesión nuevamente.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Protección de propósito: un token de password_reset NO puede utilizarse como token de acceso
    if payload.get("purpose") and payload.get("purpose") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tipo de credencial inválido para autenticación.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        user_id = int(payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identificador de usuario inválido en token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o cuenta eliminada.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta cuenta ha sido suspendida por un administrador. Contacta a soporte."
        )

    # Verificación de invalidación de sesiones (token_version)
    if payload.get("token_version") is not None and user.token_version is not None:
        if payload.get("token_version") != user.token_version:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Sesión revocada debido a un cambio de credenciales. Por favor inicia sesión nuevamente.",
                headers={"WWW-Authenticate": "Bearer"}
            )

    return user

def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Verificación criptográfica y estricta de autorización SuperAdmin.
    Garantiza que ningún usuario normal ni cuenta suspendida acceda a datos protegidos de otros usuarios.
    """
    if not current_user or not getattr(current_user, "is_admin", False):
        logger.warning(
            f"Intento no autorizado de acceso admin bloqueado por usuario ID: {getattr(current_user, 'id', 'Desconocido')} ({getattr(current_user, 'email', 'Sin correo')})"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido: Se requieren privilegios de Administrador para esta operación.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return current_user

def get_optional_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Retorna el usuario si el token es válido, o None sin disparar excepción 401."""
    if not auth or not auth.credentials:
        return None
    payload = decode_access_token(auth.credentials)
    if not payload or "sub" not in payload:
        return None
    try:
        user_id = int(payload["sub"])
        return db.query(User).filter(User.id == user_id).first()
    except Exception:
        return None
