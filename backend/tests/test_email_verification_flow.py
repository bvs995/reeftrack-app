"""
AquaPulse - Pruebas de Integración del Flujo de Verificación de Correo
Cubre:
1. Token válido: activa la cuenta, emite credenciales y habilita operaciones sin relogin.
2. Token ya usado: deniega con HTTP 400 avisando que ya fue utilizado.
3. Token expirado: deniega con HTTP 400 avisando que caducó y sugiriendo solicitar uno nuevo.
4. Flujo completo con EMAIL_PROVIDER=console sin fuga de tokens en logs.
"""
import os
import re
import pytest
import logging
from datetime import timedelta
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.main import app, auth_attempts
from backend.database import SessionLocal
from backend.models import User, Tank, RateLimitRecord
from backend.auth import (
    hash_password,
    create_email_verification_token,
    create_access_token,
)
from backend.services.email_service import (
    MockEmailProvider,
    set_email_provider,
    get_email_provider,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_test_environment():
    auth_attempts.clear()
    db = SessionLocal()
    try:
        db.query(RateLimitRecord).delete()
        test_emails = [
            "valid_token_user@aquapulse.io",
            "used_token_user@aquapulse.io",
            "expired_token_user@aquapulse.io",
            "console_flow_user@aquapulse.io",
        ]
        for em in test_emails:
            u = db.query(User).filter(User.email == em).first()
            if u:
                db.delete(u)
        db.commit()
    finally:
        db.close()

    mock_prov = MockEmailProvider(from_email="noreply@aquapulse.io")
    set_email_provider(mock_prov)
    yield mock_prov
    mock_prov.clear()
    set_email_provider(None)


class TestEmailVerificationTokensFlow:
    """Pruebas del ciclo de vida de tokens de verificación: válido, ya usado y expirado."""

    def test_valid_token_activates_account_and_enables_immediate_operations(self, clean_test_environment):
        """
        1. Token válido:
        - El endpoint /api/auth/verify-email activa la cuenta.
        - Retorna access_token y user con email_verified=True e is_active=True.
        - El usuario puede usar de inmediato el token devuelto para crear/listar tanques sin relogin.
        """
        email = "valid_token_user@aquapulse.io"
        password = "SecurePassword123!"

        with patch.dict(os.environ, {"REQUIRE_EMAIL_VERIFICATION": "true", "FRONTEND_URL": "http://localhost:5173"}):
            # Registrar usuario (queda email_verified=False e is_active=False)
            reg_res = client.post(
                "/api/auth/register",
                json={"email": email, "password": password, "full_name": "Valid User"},
            )
            assert reg_res.status_code == 201

            # Obtener el token enviado por correo
            sent = clean_test_environment.get_sent_emails()
            assert len(sent) == 1
            body = sent[0].text_body
            match = re.search(r"verify_email_token=([A-Za-z0-9_.\-]+)", body)
            assert match is not None
            token = match.group(1)

            # Consumir el token válido en /api/auth/verify-email
            verify_res = client.post(f"/api/auth/verify-email?token={token}")
            assert verify_res.status_code == 200
            data = verify_res.json()
            assert data.get("ok") is True
            assert "access_token" in data
            assert data["user"]["email_verified"] is True
            assert data["user"]["is_active"] is True

            # Verificar cookie HttpOnly de refresh token
            assert "aquapulse_refresh_token" in verify_res.cookies

            # Usar el access_token devuelto inmediatamente para operar sin relogin
            auth_headers = {"Authorization": f"Bearer {data['access_token']}"}
            tanks_res = client.get("/api/tanks", headers=auth_headers)
            assert tanks_res.status_code == 200
            tanks_data = tanks_res.json()
            assert len(tanks_data) >= 1
            tank_id = tanks_data[0]["id"]

            # Registrar una medición en el tanque del usuario inmediatamente tras verificar
            meas_res = client.post(
                "/api/measurements",
                headers=auth_headers,
                json={
                    "tank_id": tank_id,
                    "kh": 8.2,
                    "ph": 8.2,
                },
            )
            assert meas_res.status_code in (200, 201)
            assert meas_res.json()["tank_id"] == tank_id

    def test_already_used_token_is_rejected(self, clean_test_environment):
        """
        2. Token ya usado:
        - Al reintentar verificar con un token de una cuenta ya verificada,
          el endpoint debe rechazar la solicitud con HTTP 400 Bad Request.
        """
        email = "used_token_user@aquapulse.io"
        db = SessionLocal()
        user = User(
            email=email,
            hashed_password=hash_password("Pass123!"),
            is_active=False,
            email_verified=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Generar token
        token = create_email_verification_token(user.email, user.id)
        db.close()

        # Primer uso: exitoso
        first_use_res = client.post(f"/api/auth/verify-email?token={token}")
        assert first_use_res.status_code == 200
        assert first_use_res.json().get("ok") is True

        # Segundo uso (token ya usado): rechazado con 400 Bad Request
        second_use_res = client.post(f"/api/auth/verify-email?token={token}")
        assert second_use_res.status_code == 400
        detail = second_use_res.json().get("detail", "")
        assert "ya fue utilizado" in detail or "ya ha sido verificado" in detail

    def test_expired_token_is_rejected(self, clean_test_environment):
        """
        3. Token expirado:
        - Si el token ha superado su vigencia (24h), el backend debe retornar
          HTTP 400 Bad Request con mensaje indicando expiración.
        """
        email = "expired_token_user@aquapulse.io"
        db = SessionLocal()
        user = User(
            email=email,
            hashed_password=hash_password("Pass123!"),
            is_active=False,
            email_verified=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Token con expiración en el pasado (-10 segundos)
        expired_token = create_email_verification_token(
            email=user.email,
            user_id=user.id,
            expires_delta=timedelta(seconds=-10),
        )
        db.close()

        res = client.post(f"/api/auth/verify-email?token={expired_token}")
        assert res.status_code == 400
        detail = res.json().get("detail", "")
        assert "expirado" in detail.lower()


class TestConsoleEmailProviderIntegration:
    """Verifica el flujo con EMAIL_PROVIDER=console."""

    def test_flow_with_console_provider_does_not_leak_tokens_in_logs(self):
        from backend.services.email_service import logger as email_logger, ConsoleEmailProvider
        console_prov = ConsoleEmailProvider(from_email="noreply@aquapulse.io")
        set_email_provider(console_prov)

        with patch.object(email_logger, "info") as mock_info:
            with patch.dict(os.environ, {
                "REQUIRE_EMAIL_VERIFICATION": "true",
                "FRONTEND_URL": "http://localhost:5173",
            }):
                email = "console_flow_user@aquapulse.io"
                reg_res = client.post(
                    "/api/auth/register",
                    json={"email": email, "password": "Password123!", "full_name": "Console User"},
                )
                assert reg_res.status_code == 201

                # Verificar que en los logs de consola no se filtró el token ni el enlace completo
                assert mock_info.called
                all_logs = " ".join([call.args[0] for call in mock_info.call_args_list if call.args])
                assert "verify_email_token=" not in all_logs
                assert "http://localhost:5173/?verify_email_token=" not in all_logs
                assert "ConsoleEmail" in all_logs

            # Verificar que la cuenta se puede activar con un token legítimo
            db = SessionLocal()
            user = db.query(User).filter(User.email == email).first()
            assert user.email_verified is False
            token = create_email_verification_token(user.email, user.id)
            db.close()

            verify_res = client.post(f"/api/auth/verify-email?token={token}")
            assert verify_res.status_code == 200
            assert verify_res.json()["user"]["email_verified"] is True
