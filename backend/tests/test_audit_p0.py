import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import SessionLocal
from backend.models import User, PasswordResetToken
from backend.auth import hash_password, create_access_token, create_password_reset_token

client = TestClient(app)

class TestAuditP0Point1:
    """Tests para Punto 1: Forgot Password seguro, de un solo uso e invalidación de sesiones."""

    def setup_method(self):
        from backend.main import auth_attempts
        auth_attempts.clear()
        db = SessionLocal()
        # Limpiar tokens y usuario previo
        db.query(PasswordResetToken).delete()
        user = db.query(User).filter(User.email == "p0_forgot_user@aquapulse.io").first()
        if user:
            db.delete(user)
        db.commit()

        # Crear usuario de prueba
        test_user = User(
            email="p0_forgot_user@aquapulse.io",
            hashed_password=hash_password("OldPassword123!"),
            full_name="P0 Test User",
            is_active=True,
            token_version=1
        )
        db.add(test_user)
        db.commit()
        db.close()

    def test_forgot_password_response_never_contains_tokens_or_urls(self):
        """La respuesta de /api/auth/forgot-password nunca debe filtrar tokens ni URLs de dev."""
        res = client.post("/api/auth/forgot-password", json={"email": "p0_forgot_user@aquapulse.io"})
        assert res.status_code == 200
        data = res.json()
        assert "reset_token_dev" not in data, "La respuesta NO debe incluir reset_token_dev"
        assert "reset_url_dev" not in data, "La respuesta NO debe incluir reset_url_dev"
        assert "reset_token" not in data, "La respuesta NO debe incluir reset_token"
        assert "token" not in data, "La respuesta NO debe incluir token"
        assert data.get("ok") is True

    def test_forgot_password_unknown_email_is_neutral(self):
        """Solicitar restablecimiento para correo no existente responde exactamente igual (OWASP Anti-Enumeración)."""
        res = client.post("/api/auth/forgot-password", json={"email": "nonexistent_email_404@aquapulse.io"})
        assert res.status_code == 200
        data = res.json()
        assert data.get("ok") is True
        assert "reset_token" not in data
        assert "reset_url" not in data

    def test_reset_token_is_single_use(self):
        """Un token de reseteo solo puede utilizarse una única vez."""
        db = SessionLocal()
        user = db.query(User).filter(User.email == "p0_forgot_user@aquapulse.io").first()
        
        # Generar solicitud
        res = client.post("/api/auth/forgot-password", json={"email": user.email})
        assert res.status_code == 200
        
        # Obtener el registro del token de la base de datos
        token_record = db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).order_by(PasswordResetToken.id.desc()).first()
        assert token_record is not None, "El token de reseteo debe registrarse en la BD"
        assert token_record.used_at is None, "El token debe estar sin usar inicialmente"

        # Simular uso con token generado para el mismo user y jti
        token_jwt, _, _ = create_password_reset_token(user.email, user.id)
        # Sincronizamos el registro en BD para que coincida con el JTI del token_jwt generado
        import jwt
        from backend.auth import JWT_SECRET, JWT_ALGORITHM
        payload = jwt.decode(token_jwt, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        token_record.jti = payload["jti"]
        db.commit()

        # Primer uso -> Exitoso
        res_reset1 = client.post("/api/auth/reset-password", json={
            "token": token_jwt,
            "new_password": "NewValidPassword123!"
        })
        assert res_reset1.status_code == 200, f"Error en primer reseteo: {res_reset1.text}"

        # Segundo uso con el mismo token -> Debe fallar con 400 (Token ya utilizado)
        res_reset2 = client.post("/api/auth/reset-password", json={
            "token": token_jwt,
            "new_password": "AnotherNewPassword123!"
        })
        assert res_reset2.status_code == 400
        assert "utilizado" in res_reset2.json()["detail"].lower()
        db.close()

    def test_password_change_invalidates_all_prior_sessions(self):
        """Cambiar la contraseña debe invalidar todos los tokens de sesión previos (token_version)."""
        db = SessionLocal()
        user = db.query(User).filter(User.email == "p0_forgot_user@aquapulse.io").first()
        
        # Generar access token con token_version actual
        old_access_token = create_access_token({
            "sub": str(user.id),
            "email": user.email,
            "token_version": user.token_version
        })
        
        # Verificar que el token viejo funciona antes del reseteo
        res_before = client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_access_token}"})
        assert res_before.status_code == 200

        # Crear y usar token de reseteo
        token_jwt, jti, expire = create_password_reset_token(user.email, user.id)
        import hashlib
        token_hash = hashlib.sha256(token_jwt.encode()).hexdigest()
        reset_record = PasswordResetToken(user_id=user.id, token_hash=token_hash, jti=jti, expires_at=expire)
        db.add(reset_record)
        db.commit()

        res_reset = client.post("/api/auth/reset-password", json={
            "token": token_jwt,
            "new_password": "BrandNewPassword123!"
        })
        assert res_reset.status_code == 200

        # Verificar que la sesión previa fue revocada inmediatamente
        res_after = client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_access_token}"})
        assert res_after.status_code == 401
        assert "revocada" in res_after.json()["detail"].lower()
        db.close()


class TestAuditP0Point2:
    """Tests para Punto 2: Eliminación de auto-admin por correo y verificación de email."""

    def setup_method(self):
        from backend.main import auth_attempts
        auth_attempts.clear()
        db = SessionLocal()
        for email in ["paliyo995@gmail.com", "verify_me@aquapulse.io"]:
            u = db.query(User).filter(User.email == email).first()
            if u:
                db.delete(u)
        db.commit()
        db.close()

    def test_no_auto_admin_on_register(self):
        """Registrarse con paliyo995@gmail.com o cualquier correo NUNCA otorga admin automáticamente."""
        res = client.post("/api/auth/register", json={
            "email": "paliyo995@gmail.com",
            "password": "SecurePassword123!",
            "full_name": "Test User"
        })
        assert res.status_code in (201, 200)

        db = SessionLocal()
        user = db.query(User).filter(User.email == "paliyo995@gmail.com").first()
        assert user is not None
        assert user.is_admin is False, "El usuario NUNCA debe ser administrador automáticamente al registrarse"
        assert not hasattr(app.state, "AUTO_ADMIN_EMAILS") or not hasattr(app, "AUTO_ADMIN_EMAILS")
        db.close()

    def test_no_auto_admin_on_login(self):
        """Iniciar sesión con paliyo995@gmail.com NUNCA promueve a admin automáticamente."""
        db = SessionLocal()
        user = User(
            email="paliyo995@gmail.com",
            hashed_password=hash_password("SecurePassword123!"),
            is_admin=False,
            is_active=True
        )
        db.add(user)
        db.commit()
        db.close()

        res = client.post("/api/auth/login", json={
            "email": "paliyo995@gmail.com",
            "password": "SecurePassword123!"
        })
        assert res.status_code == 200

        db = SessionLocal()
        user_after = db.query(User).filter(User.email == "paliyo995@gmail.com").first()
        assert user_after.is_admin is False, "El login NUNCA debe auto-promover a administrador"
        db.close()

    def test_email_verification_flow(self):
        """El registro emite token de verificación y la cuenta se activa tras verificar el correo."""
        res = client.post("/api/auth/register", json={
            "email": "verify_me@aquapulse.io",
            "password": "SecurePassword123!",
            "full_name": "Verify Me"
        })
        assert res.status_code in (201, 200)

        # Verificar endpoint de verificación
        from backend.auth import create_email_verification_token
        db = SessionLocal()
        user = db.query(User).filter(User.email == "verify_me@aquapulse.io").first()
        token = create_email_verification_token(user.email, user.id)

        # Consumir verificación
        verify_res = client.post(f"/api/auth/verify-email?token={token}")
        assert verify_res.status_code == 200
        assert verify_res.json().get("ok") is True

        db.refresh(user)
        assert user.email_verified is True
        assert user.is_active is True
        db.close()
