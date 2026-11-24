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
