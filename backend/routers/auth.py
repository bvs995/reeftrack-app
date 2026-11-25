"""
AquaPulse - Router de Autenticación, Sesiones y Gestión de Cuenta (P2.17)
"""
import os
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Header, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import (
    User,
    RefreshToken,
    PasswordResetToken,
    UserDailyQuota,
    Tank,
    Measurement,
    MaintenanceTask,
    WaterChange,
    PushSubscription,
    DiagnosticAudit,
    DiagnosticFeedback,
    UserRegister,
    UserLogin,
    UserUpdate,
    UserResponse,
    TokenResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    PasswordResetResponse,
    ResendVerificationRequest,
    VerifyEmailRequest,
    AccountDeleteRequest,
    check_password_complexity,
)
from backend.services.email_service import mask_email
from backend.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
    create_password_reset_token,
    verify_password_reset_token,
    send_password_reset_email,
    create_email_verification_token,
    verify_email_verification_token,
    send_email_verification,
    get_current_user,
    REFRESH_TOKEN_EXPIRE_DAYS,
)
from backend.rate_limits import check_auth_rate_limit

logger = logging.getLogger("aquapulse.routers.auth")
is_production = os.getenv("ENVIRONMENT", "development") == "production"

router = APIRouter(tags=["Autenticación"])


@router.post(
    "/api/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar una nueva cuenta de usuario"
)
def register_user(
    payload: UserRegister,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Crea una nueva cuenta de usuario, inicializa su primer acuario y emite token JWT con refresh token en cookie."""
    check_auth_rate_limit(request, email=payload.email)
    normalized_email = payload.email.strip().lower()

    existing_user = db.query(User).filter(User.email == normalized_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una cuenta registrada con este correo electrónico."
        )

    require_verification = os.getenv("REQUIRE_EMAIL_VERIFICATION", "false").lower() in ("true", "1", "yes")

    new_user = User(
        email=normalized_email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name.strip() if payload.full_name else None,
        unit_preference="liters",
        subscription_tier="free",
        is_admin=False,
        is_active=False if require_verification else True,
        email_verified=False,
        created_at=datetime.now(timezone.utc)
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    verify_token = create_email_verification_token(new_user.email, new_user.id)
    frontend_base = os.getenv("FRONTEND_URL", "").rstrip("/") or "http://localhost:5173"
    verify_url = f"{frontend_base}/?verify_email_token={verify_token}"
    sent = send_email_verification(new_user.email, verify_url)
    if not sent:
        logger.error(f"Fallo al enviar correo de verificación inicial al registrar usuario {mask_email(new_user.email)}")

    default_tank = Tank(
        user_id=new_user.id,
        name="Mi Acuario Principal",
        tank_type="reef",
        volume_liters=280.0,
        notes="Acuario inicial creado automáticamente"
    )
    db.add(default_tank)
    db.commit()

    access_token = create_access_token({
        "sub": str(new_user.id),
        "email": new_user.email,
        "token_version": new_user.token_version or 1
    })
    raw_rt, rt_hash, rt_jti, rt_fam, rt_exp = create_refresh_token(new_user.id)
    new_rf = RefreshToken(
        user_id=new_user.id,
        token_hash=rt_hash,
        jti=rt_jti,
        family_id=rt_fam,
        expires_at=rt_exp
    )
    db.add(new_rf)
    db.commit()

    response.set_cookie(
        key="refresh_token",
        value=raw_rt,
        httponly=True,
        secure=is_production,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/auth"
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        refresh_token=None,
        user=UserResponse.model_validate(new_user)
    )


@router.post(
    "/api/auth/login",
    response_model=TokenResponse,
    summary="Iniciar sesión con correo y contraseña"
)
def login_user(
    payload: UserLogin,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Valida credenciales y emite token JWT con refresh token en cookie HttpOnly. Evita enumeración de usuarios."""
    check_auth_rate_limit(request, email=payload.email)
    normalized_email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()

    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas. Verifica tu correo y contraseña.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        if not user.email_verified and os.getenv("REQUIRE_EMAIL_VERIFICATION", "false").lower() in ("true", "1", "yes"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Debes verificar tu correo electrónico antes de activar tu cuenta. Hemos enviado un enlace a tu correo."
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta cuenta ha sido suspendida o no está activa. Contacta a soporte."
        )

    access_token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "token_version": user.token_version or 1
    })
    raw_rt, rt_hash, rt_jti, rt_fam, rt_exp = create_refresh_token(user.id)
    new_rf = RefreshToken(
        user_id=user.id,
        token_hash=rt_hash,
        jti=rt_jti,
        family_id=rt_fam,
        expires_at=rt_exp
    )
    db.add(new_rf)
    db.commit()

    response.set_cookie(
        key="refresh_token",
        value=raw_rt,
        httponly=True,
        secure=is_production,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/auth"
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        refresh_token=None,
        user=UserResponse.model_validate(user)
    )


@router.post(
    "/api/auth/refresh",
    response_model=TokenResponse,
    summary="Renovar token de acceso usando refresh token rotativo en cookie o cabecera"
)
def refresh_access_token(
    request: Request,
    response: Response,
    x_refresh_token: Optional[str] = Header(None, alias="X-Refresh-Token"),
    db: Session = Depends(get_db)
):
    """Verifica el refresh token de la cookie HttpOnly (o cabecera) y rota emitiendo un nuevo par de tokens."""
    cookie_token = request.cookies.get("refresh_token")
    token_to_verify = cookie_token or x_refresh_token

    if not token_to_verify:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No se proporcionó refresh token válido en cookie HttpOnly o cabecera X-Refresh-Token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = verify_refresh_token(token_to_verify)
    user_id = int(payload["sub"])

    t_hash = hashlib.sha256(token_to_verify.encode("utf-8")).hexdigest()
    token_record = db.query(RefreshToken).filter(RefreshToken.token_hash == t_hash).first()

    if not token_record:
        response.delete_cookie(key="refresh_token", path="/api/auth")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión no encontrada o token de refresco no reconocido.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Detección de reutilización (Token Reuse Detection)
    if token_record.revoked_at is not None:
        now_utc = datetime.now(timezone.utc)
        db.query(RefreshToken).filter(
            RefreshToken.family_id == token_record.family_id,
            RefreshToken.revoked_at.is_(None)
        ).update({"revoked_at": now_utc})

        user = db.query(User).filter(User.id == token_record.user_id).first()
        if user:
            user.token_version = (user.token_version or 1) + 1
        db.commit()

        response.delete_cookie(key="refresh_token", path="/api/auth")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Alerta de seguridad: intento de reutilización de sesión. Todas las sesiones activas han sido revocadas.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    # Rotar: revocar token actual
    token_record.revoked_at = datetime.now(timezone.utc)

    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        db.commit()
        response.delete_cookie(key="refresh_token", path="/api/auth")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesión expirada o usuario inactivo. Inicie sesión nuevamente.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    new_raw_rt, new_hash, new_jti, fam_id, new_exp = create_refresh_token(
        user.id,
        family_id=token_record.family_id
    )
    new_record = RefreshToken(
        user_id=user.id,
        token_hash=new_hash,
        jti=new_jti,
        family_id=fam_id,
        expires_at=new_exp
    )
    db.add(new_record)
    db.commit()

    new_access_token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "token_version": user.token_version or 1
    })

    response.set_cookie(
        key="refresh_token",
        value=new_raw_rt,
        httponly=True,
        secure=is_production,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/auth"
    )

    return TokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        refresh_token=None,
        user=UserResponse.model_validate(user)
    )


@router.post(
    "/api/auth/logout",
    summary="Cerrar sesión e invalidar la cookie del refresh token"
)
def logout_user(
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Revoca el refresh token en el servidor (en BD) y limpia la cookie HttpOnly."""
    cookie_token = request.cookies.get("refresh_token")
    if cookie_token:
        try:
            t_hash = hashlib.sha256(cookie_token.encode("utf-8")).hexdigest()
            record = db.query(RefreshToken).filter(
                RefreshToken.token_hash == t_hash,
                RefreshToken.revoked_at.is_(None)
            ).first()
            if record:
                record.revoked_at = datetime.now(timezone.utc)
                db.commit()
        except Exception as e:
            logger.warning(f"Error al revocar refresh token en logout: {e}")

    response.delete_cookie(key="refresh_token", path="/api/auth")
    return {"status": "success", "message": "Sesión cerrada correctamente."}


@router.post(
    "/api/auth/forgot-password",
    response_model=PasswordResetResponse,
    summary="Solicitar enlace para restablecer contraseña"
)
def forgot_password(
    payload: ForgotPasswordRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Genera un token firmado temporal y emite un enlace de restablecimiento.
    Por seguridad (OWASP), siempre responde de manera neutral para evitar enumeración de correos.
    El token es de un solo uso y se envía por proveedor transaccional SMTP sin exponerlo en logs.
    """
    check_auth_rate_limit(request, email=payload.email)
    normalized_email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()

    frontend_base = os.getenv("FRONTEND_URL", "").rstrip("/") or "http://localhost:5173"

    if user and user.is_active:
        reset_token, jti, expire = create_password_reset_token(user.email, user.id)
        reset_url = f"{frontend_base}/?reset_token={reset_token}"
        token_hash = hashlib.sha256(reset_token.encode("utf-8")).hexdigest()

        reset_record = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            jti=jti,
            expires_at=expire
        )
        db.add(reset_record)
        db.commit()

        sent = send_password_reset_email(user.email, reset_url)
        if not sent:
            logger.error(f"Fallo al enviar correo de restablecimiento de contraseña a {mask_email(user.email)}")

    logger.info("Solicitud de restablecimiento de contraseña procesada con respuesta neutral.")
    return PasswordResetResponse(
        ok=True,
        message="Si tu correo está registrado, recibirás un enlace seguro para restablecer tu contraseña."
    )


@router.post(
    "/api/auth/reset-password",
    response_model=PasswordResetResponse,
    summary="Restablecer la contraseña usando el token seguro"
)
def reset_password(
    request: Request,
    payload: Optional[ResetPasswordRequest] = None,
    db: Session = Depends(get_db)
):
    """Valida el token firmado de un solo uso en el cuerpo JSON, actualiza contraseña con bcrypt e invalida todas las sesiones previas."""
    if request.query_params.get("token") or request.query_params.get("reset_token"):
        logger.warning("Intento de restablecimiento rechazado: token transmitido en query string en lugar del cuerpo JSON.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Por motivos de seguridad, el token de restablecimiento no debe enviarse en la URL. Envíalo en el cuerpo JSON de la petición."
        )

    if not payload or not payload.token or not payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El token de restablecimiento y la nueva contraseña deben enviarse en el cuerpo JSON de la petición."
        )

    try:
        check_password_complexity(payload.new_password)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    token_data = verify_password_reset_token(payload.token)
    user_id = int(token_data["sub"])
    jti = token_data.get("jti")

    reset_record = db.query(PasswordResetToken).filter(
        PasswordResetToken.jti == jti,
        PasswordResetToken.user_id == user_id
    ).first()

    now = datetime.now(timezone.utc)
    if not reset_record or reset_record.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este enlace de restablecimiento ya ha sido utilizado o no es válido. Solicita uno nuevo."
        )

    exp = reset_record.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El enlace de restablecimiento ha expirado. Por favor solicita uno nuevo."
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta se encuentra suspendida. Contacta a soporte."
        )

    user.hashed_password = hash_password(payload.new_password)
    user.token_version = (user.token_version or 1) + 1
    reset_record.used_at = now
    db.commit()

    logger.info("Contraseña actualizada y sesiones anteriores revocadas para usuario.")

    return PasswordResetResponse(
        ok=True,
        message="Contraseña actualizada exitosamente. Ya puedes iniciar sesión con tu nueva contraseña."
    )


@router.post(
    "/api/auth/verify-email",
    summary="Verificar correo electrónico para activar la cuenta"
)
def verify_email(
    request: Request,
    response: Response,
    payload: Optional[VerifyEmailRequest] = None,
    db: Session = Depends(get_db)
):
    """
    Valida el token de verificación y activa la cuenta del usuario.
    El token DEBE enviarse en el cuerpo JSON de la petición para evitar que quede registrado en los logs de acceso.
    Si el token se envía en la URL (?token=...), se rechaza de inmediato con HTTP 400.
    """
    if request.query_params.get("token") or request.query_params.get("verify_email_token"):
        logger.warning("Intento de verificación rechazado: token transmitido en query string en lugar del cuerpo JSON.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Por motivos de seguridad, el token de verificación no debe enviarse en la URL. Envíalo en el cuerpo JSON de la petición."
        )

    if not payload or not payload.token or not payload.token.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El token de verificación debe enviarse en el cuerpo JSON de la petición."
        )

    clean_token = payload.token.strip()

    token_data = verify_email_verification_token(clean_token)
    user_id = int(token_data["sub"])

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado."
        )

    if user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este enlace de verificación ya fue utilizado o el correo ya ha sido verificado."
        )

    user.email_verified = True
    user.is_active = True
    db.commit()
    db.refresh(user)

    access_token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "token_version": user.token_version or 1
    })
    raw_rt, rt_hash, rt_jti, rt_fam, rt_exp = create_refresh_token(user.id)
    new_rf = RefreshToken(
        user_id=user.id,
        token_hash=rt_hash,
        jti=rt_jti,
        family_id=rt_fam,
        expires_at=rt_exp
    )
    db.add(new_rf)
    db.commit()

    response.set_cookie(
        key="aquapulse_refresh_token",
        value=raw_rt,
        httponly=True,
        secure=is_production,
        samesite="lax",
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/api/auth",
    )

    logger.info(f"Correo electrónico verificado exitosamente para usuario ID {user.id}")
    return {
        "ok": True,
        "message": "Correo electrónico verificado exitosamente. Tu cuenta está activa y lista para usar.",
        "access_token": access_token,
        "user": UserResponse.model_validate(user).model_dump()
    }


@router.post(
    "/api/auth/resend-verification",
    summary="Reenviar correo de verificación de cuenta"
)
def resend_verification_email(
    payload: ResendVerificationRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Reenvía un correo con un nuevo enlace de activación si la cuenta existe y no está verificada.
    La respuesta es siempre neutra para evitar enumeración de usuarios, pero si el envío falla o se supera el límite de intentos,
    se registra un ERROR claro y no se bloquea en silencio.
    """
    check_auth_rate_limit(request, email=payload.email)
    normalized_email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()

    if user and not user.email_verified:
        verify_token = create_email_verification_token(user.email, user.id)
        frontend_base = os.getenv("FRONTEND_URL", "").rstrip("/") or "http://localhost:5173"
        verify_url = f"{frontend_base}/?verify_email_token={verify_token}"
        sent = send_email_verification(user.email, verify_url)
        if not sent:
            logger.error(f"Fallo al reenviar correo de verificación a {mask_email(user.email)}: el proveedor rechazó el envío o no está configurado.")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No se pudo enviar el correo de verificación en este momento por un fallo en el servicio de correo. Por favor contacta a soporte o intenta más tarde."
            )

    return {
        "ok": True,
        "message": "Si la cuenta existe y está pendiente de verificación, recibirás un nuevo enlace de activación."
    }


@router.get(
    "/api/auth/me",
    response_model=UserResponse,
    summary="Obtener perfil del usuario autenticado"
)
def get_user_profile(current_user: User = Depends(get_current_user)):
    """Retorna información del usuario autenticado actual."""
    return UserResponse.model_validate(current_user)


@router.put(
    "/api/auth/me",
    response_model=UserResponse,
    summary="Actualizar perfil y preferencias de la cuenta"
)
def update_user_profile(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Actualiza nombre o preferencia de unidades de medida (liters / gallons)."""
    if payload.full_name is not None:
        current_user.full_name = payload.full_name.strip()
    if payload.unit_preference is not None:
        current_user.unit_preference = payload.unit_preference

    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.get(
    "/api/user/export",
    summary="Exportar todos los datos personales del usuario (Derecho de portabilidad GDPR)"
)
def export_user_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Genera una copia íntegra y portable de todos los datos del usuario en formato JSON."""
    tanks = db.query(Tank).filter(Tank.user_id == current_user.id).all()
    measurements = db.query(Measurement).filter(Measurement.user_id == current_user.id).all()
    tasks = db.query(MaintenanceTask).filter(MaintenanceTask.user_id == current_user.id).all()
    water_changes = db.query(WaterChange).filter(WaterChange.user_id == current_user.id).all()
    push_subs = db.query(PushSubscription).filter(PushSubscription.user_id == current_user.id).all()

    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "unit_preference": current_user.unit_preference,
            "subscription_tier": current_user.subscription_tier,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None
        },
        "tanks": [
            {
                "id": t.id,
                "name": t.name,
                "tank_type": t.tank_type,
                "volume_liters": t.volume_liters,
                "reef_profile": t.reef_profile,
                "dosing_method": t.dosing_method,
                "lighting_par": t.lighting_par,
                "flow_profile": t.flow_profile,
                "notes": t.notes,
                "created_at": t.created_at.isoformat() if t.created_at else None
            }
            for t in tanks
        ],
        "measurements": [
            {
                "id": m.id,
                "tank_id": m.tank_id,
                "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                "ph": m.ph,
                "kh": m.kh,
                "calcium": m.calcium,
                "magnesium": m.magnesium,
                "nitrate": m.nitrate,
                "phosphate": m.phosphate,
                "temperature": m.temperature,
                "salinity": m.salinity,
                "notes": m.notes
            }
            for m in measurements
        ],
        "maintenance_tasks": [
            {
                "id": tk.id,
                "task_type": tk.task_type,
                "frequency_days": tk.frequency_days,
                "is_enabled": tk.is_enabled
            }
            for tk in tasks
        ],
        "water_changes": [
            {
                "id": wc.id,
                "volume_liters": wc.volume_liters,
                "percentage": wc.percentage,
                "performed_at": wc.performed_at.isoformat() if wc.performed_at else None
            }
            for wc in water_changes
        ],
        "push_subscriptions": [
            {"id": ps.id, "endpoint": ps.endpoint}
            for ps in push_subs
        ]
    }


@router.delete(
    "/api/user/account",
    summary="Eliminar permanentemente o programar borrado de la cuenta de usuario (Derecho al olvido GDPR / P2.16)"
)
def delete_user_account(
    payload: AccountDeleteRequest,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Elimina la cuenta del usuario previa confirmación de contraseña (P2.16).
    Soporta periodo de gracia opcional (ej: 7 días). Si grace_period_days == 0,
    elimina inmediatamente en cascada estricta el usuario y absolutamente todos sus registros asociados,
    incluyendo diagnósticos, auditorías, feedback y notificaciones push.
    """
    if not payload.password or not verify_password(payload.password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Contraseña incorrecta. Se requiere confirmación de contraseña para eliminar la cuenta."
        )

    user_id = current_user.id
    email = current_user.email

    # Periodo de gracia opcional (P2.16)
    if payload.grace_period_days and payload.grace_period_days > 0:
        scheduled_date = datetime.now(timezone.utc) + timedelta(days=payload.grace_period_days)
        current_user.is_active = False
        current_user.deletion_scheduled_at = scheduled_date
        current_user.token_version = (current_user.token_version or 1) + 1

        db.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
        db.commit()

        response.delete_cookie(key="refresh_token", path="/api/auth")
        logger.info(f"Cuenta de {email} (ID: {user_id}) programada para eliminación en {payload.grace_period_days} días ({scheduled_date.isoformat()}).")
        return {
            "status": "scheduled_for_deletion",
            "message": f"Tu cuenta ha sido desactivada y se eliminará permanentemente tras el periodo de gracia de {payload.grace_period_days} días.",
            "deletion_scheduled_at": scheduled_date.isoformat()
        }

    # Borrado inmediato en cascada total
    db.query(DiagnosticFeedback).filter(DiagnosticFeedback.user_id == user_id).delete()
    db.query(DiagnosticAudit).filter(DiagnosticAudit.user_id == user_id).delete()
    db.query(PushSubscription).filter(PushSubscription.user_id == user_id).delete()
    db.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
    db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user_id).delete()
    db.query(UserDailyQuota).filter(UserDailyQuota.user_id == user_id).delete()

    db.delete(current_user)
    db.commit()

    response.delete_cookie(key="refresh_token", path="/api/auth")
    logger.info(f"Cuenta y datos eliminados íntegramente para el usuario {email} (ID: {user_id}).")
    return {
        "status": "success",
        "message": "Tu cuenta y todos tus datos (tanques, mediciones, tareas, auditorías de IA y suscripciones) han sido eliminados de forma permanente."
    }
