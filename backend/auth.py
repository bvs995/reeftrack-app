import os
import logging
from datetime import datetime, timedelta
from typing import Optional
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

# Clave secreta robusta de 64 caracteres para firma JWT
JWT_SECRET = os.environ.get(
    "JWT_SECRET",
    "aquapulse_marine_super_secret_jwt_encryption_key_reef_freemium_2026_token"
)
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

security = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    """Genera hash seguro de contraseña usando bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si la contraseña en texto plano coincide con el hash almacenado."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception as e:
        logger.warning(f"Error verificando contraseña: {e}")
        return False

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Genera un token JWT firmado con expiración estándar."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

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

    # Auto-promoción a Administrador si coincide con paliyo995@gmail.com o ADMIN_EMAIL
    auto_admin_emails = {
        "paliyo995@gmail.com",
        os.getenv("ADMIN_EMAIL", "").strip().lower()
    } - {""}
    if user.email and user.email.lower() in auto_admin_emails and not user.is_admin:
        user.is_admin = True
        db.commit()
        db.refresh(user)

    return user

def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Verifica estrictamente que el usuario autenticado tenga privilegios de Administrador."""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido: Se requieren privilegios de Administrador para esta operación."
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
