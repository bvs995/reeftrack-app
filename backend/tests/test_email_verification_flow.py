"""
AquaReef - Pruebas de Integración del Flujo de Verificación de Correo
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
            "resend_test_user@aquapulse.io",
            "unverified_gate_user@aquapulse.io",
            "qs_reject_user@aquapulse.io",
            "email_ratelimit_user@aquapulse.io",
            "provider_failure_user@aquapulse.io",
            "zero_leak_user@aquapulse.io",
        ]
        for em in test_emails:
            u = db.query(User).filter(User.email == em).first()
            if u:
                db.delete(u)
        db.commit()
    finally:
        db.close()

    mock_prov = MockEmailProvider(from_email="no-reply@aquareef.app")
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

            # Consumir el token válido en /api/auth/verify-email mediante cuerpo JSON
            verify_res = client.post("/api/auth/verify-email", json={"token": token})
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

        # Primer uso: exitoso con cuerpo JSON
        first_use_res = client.post("/api/auth/verify-email", json={"token": token})
        assert first_use_res.status_code == 200
        assert first_use_res.json().get("ok") is True

        # Segundo uso (token ya usado): rechazado con 400 Bad Request
        second_use_res = client.post("/api/auth/verify-email", json={"token": token})
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

        res = client.post("/api/auth/verify-email", json={"token": expired_token})
        assert res.status_code == 400
        detail = res.json().get("detail", "")
        assert "expirado" in detail.lower()


class TestConsoleEmailProviderIntegration:
    """Verifica el flujo con EMAIL_PROVIDER=console."""

    def test_flow_with_console_provider_does_not_leak_tokens_in_logs(self):
        from backend.services.email_service import logger as email_logger, ConsoleEmailProvider
        console_prov = ConsoleEmailProvider(from_email="no-reply@aquareef.app")
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

            verify_res = client.post("/api/auth/verify-email", json={"token": token})
            assert verify_res.status_code == 200
            assert verify_res.json()["user"]["email_verified"] is True


class TestUnverifiedGateAndResendBehavior:
    """
    Verifica el comportamiento de la compuerta de cuentas no verificadas y el reenvío de correo:
    - POST /api/auth/resend-verification envía correo real/simulado y maneja errores / rate-limit.
    - Endpoints de datos (/api/tanks, /api/measurements) devuelven 403 si la cuenta no está verificada.
    - Al verificarse la cuenta, los datos se desbloquean inmediatamente y el perfil refleja email_verified=True.
    """

    def test_resend_verification_endpoint_and_rate_limit(self, clean_test_environment):
        mock_provider = clean_test_environment
        email = "resend_test_user@aquapulse.io"

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
        db.close()

        # 1. Reenvío exitoso
        res = client.post("/api/auth/resend-verification", json={"email": email})
        assert res.status_code == 200
        data = res.json()
        assert data.get("ok") is True
        assert len(mock_provider.sent_emails) == 1
        assert mock_provider.sent_emails[0].to_email == email
        assert "verify_email_token=" in mock_provider.sent_emails[0].text_body

        # 2. Exceso de tasa / rate limiting para verificar mensaje claro de error
        with patch("backend.rate_limits.AUTH_RATE_LIMIT_IP_MAX", 2):
            # Limpiar intentos previos para esta prueba
            auth_attempts.clear()
            # 2 llamadas permitidas
            r1 = client.post("/api/auth/resend-verification", json={"email": email})
            r2 = client.post("/api/auth/resend-verification", json={"email": email})
            assert r1.status_code == 200
            assert r2.status_code == 200

            # 3ra llamada: bloqueada con 429 Too Many Requests y mensaje claro
            r3 = client.post("/api/auth/resend-verification", json={"email": email})
            assert r3.status_code == 429
            detail = r3.json().get("detail", "")
            assert "Demasiad" in detail or "espera" in detail.lower()

    def test_unverified_account_data_endpoints_blocked_and_activated(self, clean_test_environment):
        email = "unverified_gate_user@aquapulse.io"

        with patch.dict(os.environ, {"REQUIRE_EMAIL_VERIFICATION": "true", "FRONTEND_URL": "http://localhost:5173"}):
            # Registrar usuario (email_verified=False, is_active=False)
            reg_res = client.post(
                "/api/auth/register",
                json={"email": email, "password": "GatePassword123!", "full_name": "Gate User"},
            )
            assert reg_res.status_code == 201
            reg_data = reg_res.json()
            assert reg_data["user"]["email_verified"] is False
            token = reg_data["access_token"]
            headers = {"Authorization": f"Bearer {token}"}

            # Pantallas de datos: /api/tanks bloqueado con 403
            tanks_res = client.get("/api/tanks", headers=headers)
            assert tanks_res.status_code == 403
            assert "Debes verificar tu correo" in tanks_res.json().get("detail", "")

            # Pantalla de datos: /api/measurements bloqueado con 403
            meas_res = client.post(
                "/api/measurements",
                headers=headers,
                json={"tank_id": 1, "parameter_code": "ph", "value": 8.2},
            )
            assert meas_res.status_code == 403
            assert "Debes verificar tu correo" in meas_res.json().get("detail", "")

            # Obtener token de verificación emitido durante registro
            mock_provider = clean_test_environment
            assert len(mock_provider.sent_emails) >= 1
            last_email = mock_provider.sent_emails[-1]
            token_match = re.search(r"verify_email_token=([A-Za-z0-9\-_\.]+)", last_email.text_body)
            assert token_match is not None
            verify_token = token_match.group(1)

            # Verificar la cuenta usando el token mediante cuerpo JSON
            verify_res = client.post("/api/auth/verify-email", json={"token": verify_token})
            assert verify_res.status_code == 200
            verified_data = verify_res.json()
            assert verified_data["user"]["email_verified"] is True
            new_token = verified_data["access_token"]
            new_headers = {"Authorization": f"Bearer {new_token}"}

            # Ahora los endpoints de datos responden 200 sin 403
            tanks_ok = client.get("/api/tanks", headers=new_headers)
            assert tanks_ok.status_code == 200
            assert isinstance(tanks_ok.json(), list)

            # Perfil de usuario refleja estado verificado
            me_ok = client.get("/api/auth/me", headers=new_headers)
            assert me_ok.status_code == 200
            assert me_ok.json()["email_verified"] is True


class TestEmailSecurityAndReliability:
    """
    Pruebas rigurosas de seguridad y fiabilidad:
    1. Rechazo estricto de tokens en query string (verify-email y reset-password).
    2. Cero tokens o enlaces completos en registros de logging.
    3. Registro de ERROR claro ante fallos del proveedor sin filtrar tokens.
    4. Rate limit por correo en reenvío devuelve HTTP 429 y registra ERROR.
    5. Avisos y validaciones claras de configuración al arrancar.
    6. Salida visible de ConsoleEmailProvider en la terminal de desarrollo.
    """

    def test_query_string_token_rejection_for_verify_and_reset(self, clean_test_environment):
        email = "qs_reject_user@aquapulse.io"
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
        token = create_email_verification_token(user.email, user.id)
        db.close()

        # 1. verify-email con token solo en query string -> 400 Bad Request
        r1 = client.post(f"/api/auth/verify-email?token={token}")
        assert r1.status_code == 400
        assert "cuerpo JSON" in r1.json()["detail"]

        # 2. verify-email con query param redundante -> 400 Bad Request (rechazo estricto para evitar fuga en logs de acceso)
        r2 = client.post(f"/api/auth/verify-email?verify_email_token={token}", json={"token": token})
        assert r2.status_code == 400
        assert "cuerpo JSON" in r2.json()["detail"]

        # 3. reset-password con token en query string -> 400 Bad Request
        r3 = client.post(
            f"/api/auth/reset-password?reset_token={token}",
            json={"token": token, "new_password": "NewSecurePassword123!"}
        )
        assert r3.status_code == 400
        assert "cuerpo JSON" in r3.json()["detail"]

    def test_zero_tokens_or_links_in_application_logs(self, caplog):
        caplog.set_level(logging.DEBUG)
        email = "zero_leak_user@aquapulse.io"

        with patch.dict(os.environ, {"FRONTEND_URL": "http://localhost:5173"}):
            # Registro
            reg_res = client.post(
                "/api/auth/register",
                json={"email": email, "password": "Password123!", "full_name": "Zero Leak"},
            )
            assert reg_res.status_code == 201

            # Solicitud de restablecimiento
            client.post("/api/auth/forgot-password", json={"email": email})

            # Reenvío de verificación
            client.post("/api/auth/resend-verification", json={"email": email})

        all_logs = caplog.text
        # Ningún parámetro sensible o URL con token en el registro de la app
        assert "verify_email_token=" not in all_logs
        assert "reset_token=" not in all_logs
        assert "http://localhost:5173/?verify_email_token=" not in all_logs
        assert "http://localhost:5173/?reset_token=" not in all_logs

    def test_email_provider_failure_logs_error_without_token(self):
        from backend.services.email_service import logger as email_logger, ResendEmailProvider

        # Proveedor con API key inválida
        prov = ResendEmailProvider(api_key="re_invalid_test_key", from_email="soporte@aquapulse.io")
        with patch("backend.services.email_service.requests.post") as mock_post:
            mock_post.return_value.status_code = 401

            with patch.object(email_logger, "error") as mock_err:
                ok = prov.send_email(
                    to_email="victim@domain.com",
                    subject="Prueba de fallo",
                    html_body="<a href='http://localhost:5173/?verify_email_token=SECRET_TOKEN'>link</a>",
                    text_body="Enlace: http://localhost:5173/?verify_email_token=SECRET_TOKEN",
                )
                assert ok is False
                assert mock_err.called
                error_msgs = " ".join([call.args[0] for call in mock_err.call_args_list if call.args])
                # Debe registrar el ERROR claro
                assert "Fallo en envío de correo" in error_msgs
                # NUNCA filtrar el token ni el enlace completo
                assert "SECRET_TOKEN" not in error_msgs
                assert "verify_email_token=" not in error_msgs
                # El correo debe estar enmascarado
                assert "victim@domain.com" not in error_msgs
                assert "v****m@domain.com" in error_msgs

    def test_resend_verification_raises_503_on_provider_failure(self):
        email = "provider_failure_user@aquapulse.io"
        db = SessionLocal()
        user = User(
            email=email,
            hashed_password=hash_password("Pass123!"),
            is_active=False,
            email_verified=False,
        )
        db.add(user)
        db.commit()
        db.close()

        with patch("backend.routers.auth.send_email_verification", return_value=False):
            res = client.post("/api/auth/resend-verification", json={"email": email})
            # No falla en silencio, retorna 503 claro
            assert res.status_code == 503
            assert "fallo en el servicio de correo" in res.json()["detail"].lower()

    def test_resend_rate_limit_by_email_logs_error_and_returns_429(self):
        email = "email_ratelimit_user@aquapulse.io"
        db = SessionLocal()
        user = User(
            email=email,
            hashed_password=hash_password("Pass123!"),
            is_active=False,
            email_verified=False,
        )
        db.add(user)
        db.commit()
        db.close()

        from backend.rate_limits import logger as rate_logger
        with patch("backend.rate_limits.AUTH_RATE_LIMIT_EMAIL_MAX", 2):
            with patch.object(rate_logger, "error") as mock_log_err:
                # 2 intentos permitidos
                r1 = client.post("/api/auth/resend-verification", json={"email": email})
                r2 = client.post("/api/auth/resend-verification", json={"email": email})
                assert r1.status_code == 200
                assert r2.status_code == 200

                # 3er intento: límite excedido
                r3 = client.post("/api/auth/resend-verification", json={"email": email})
                assert r3.status_code == 429
                assert "agotado el límite de intentos" in r3.json()["detail"].lower()
                assert mock_log_err.called
                log_text = " ".join([call.args[0] for call in mock_log_err.call_args_list if call.args])
                assert "Límite de intentos de autenticación excedido" in log_text
                assert "token" not in log_text.lower()
                assert email not in log_text  # Debe estar enmascarado

    def test_startup_email_configuration_warnings_and_validation(self):
        from backend.services.email_service import check_email_configuration_on_startup, logger as email_logger

        # 1. Modo desarrollo con proveedor console
        with patch.dict(os.environ, {"ENVIRONMENT": "development", "EMAIL_PROVIDER": "console"}):
            with patch.object(email_logger, "warning") as mock_warn:
                ok = check_email_configuration_on_startup()
                assert ok is True
                assert mock_warn.called
                warn_text = " ".join([call.args[0] for call in mock_warn.call_args_list if call.args])
                assert "modo 'console'" in warn_text

        # 2. Modo desarrollo con resend sin API key
        with patch.dict(os.environ, {"ENVIRONMENT": "development", "EMAIL_PROVIDER": "resend", "EMAIL_API_KEY": ""}):
            with patch.object(email_logger, "error") as mock_err:
                ok = check_email_configuration_on_startup()
                assert ok is True
                assert mock_err.called
                err_text = " ".join([call.args[0] for call in mock_err.call_args_list if call.args])
                assert "falta la variable EMAIL_API_KEY" in err_text

        # 3. Modo producción sin configuración -> RuntimeError
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "EMAIL_PROVIDER": ""}):
            with pytest.raises(RuntimeError, match="EMAIL_PROVIDER debe estar configurada"):
                check_email_configuration_on_startup()

    def test_console_email_provider_prints_visible_banner_to_stdout(self, capsys):
        from backend.services.email_service import ConsoleEmailProvider
        prov = ConsoleEmailProvider(from_email="no-reply@aquareef.app")

        ok = prov.send_email(
            to_email="dev@aquapulse.io",
            subject="Verifica tu cuenta de desarrollo",
            html_body="<p>Enlace de desarrollo</p>",
            text_body="Abre: http://localhost:5173/?verify_email_token=dev_token_12345",
        )
        assert ok is True
        captured = capsys.readouterr()
        # En desarrollo, la terminal debe mostrar visiblemente el banner y el correo
        assert "AQUAPULSE EMAIL (CONSOLE)" in captured.out
        assert "dev@aquapulse.io" in captured.out
        assert "http://localhost:5173/?verify_email_token=dev_token_12345" in captured.out


