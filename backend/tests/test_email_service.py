"""
AquaReef - Pruebas del Servicio de Correos Transaccionales y Cuentas No Verificadas
"""
import os
import re
import pytest
import logging
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app, auth_attempts
from backend.database import SessionLocal, get_db
from backend.models import User, Tank, RateLimitRecord
from backend.auth import hash_password, create_access_token
from backend.services.email_service import (
    BaseEmailProvider,
    ResendEmailProvider,
    BrevoEmailProvider,
    SMTPEmailProvider,
    MockEmailProvider,
    set_email_provider,
    get_email_provider,
    validate_email_configuration,
    mask_email,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_mock_email_provider():
    """Configura automáticamente un MockEmailProvider antes de cada prueba y lo limpia después."""
    auth_attempts.clear()
    db = SessionLocal()
    try:
        db.query(RateLimitRecord).delete()
        test_emails = [
            "test_register_flow@aquapulse.io",
            "unverified_permissions@aquapulse.io",
            "forgot_user_flow@aquapulse.io",
            "unverified_resend@aquapulse.io",
            "logging_check@aquapulse.io",
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


class TestEmailProvidersUnit:
    """Pruebas unitarias de las clases concretas de proveedores."""

    def test_mask_email(self):
        assert mask_email("usuario@dominio.com") == "u*****o@dominio.com"
        assert mask_email("ab@dominio.com") == "a*@dominio.com"
        assert mask_email("a@dominio.com") == "a*@dominio.com"
        assert mask_email("") == "***"

    @patch("backend.services.email_service.requests")
    def test_resend_provider_success(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_requests.post.return_value = mock_resp

        provider = ResendEmailProvider(api_key="re_test_123", from_email="soporte@aquapulse.io")
        ok = provider.send_email(
            to_email="destinatario@test.com",
            subject="Asunto de Prueba",
            html_body="<p>Hola</p>",
            text_body="Hola",
        )
        assert ok is True
        mock_requests.post.assert_called_once()
        args, kwargs = mock_requests.post.call_args
        assert args[0] == "https://api.resend.com/emails"
        assert kwargs["headers"]["Authorization"] == "Bearer re_test_123"
        assert kwargs["json"]["to"] == ["destinatario@test.com"]

    @patch("backend.services.email_service.requests")
    def test_brevo_provider_success(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_requests.post.return_value = mock_resp

        provider = BrevoEmailProvider(api_key="xkeysib-test-123", from_email="soporte@aquapulse.io")
        ok = provider.send_email(
            to_email="destinatario@test.com",
            subject="Asunto Brevo",
            html_body="<p>Hola Brevo</p>",
            text_body="Hola Brevo",
        )
        assert ok is True
        mock_requests.post.assert_called_once()
        args, kwargs = mock_requests.post.call_args
        assert args[0] == "https://api.brevo.com/v3/smtp/email"
        assert kwargs["headers"]["api-key"] == "xkeysib-test-123"
        assert kwargs["json"]["to"] == [{"email": "destinatario@test.com"}]

    @patch("smtplib.SMTP")
    def test_smtp_provider_success(self, mock_smtp):
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        provider = SMTPEmailProvider(
            host="smtp.example.com",
            port=587,
            user="user@example.com",
            password="secretpassword",
            from_email="no-reply@aquareef.app",
            use_tls=True,
        )
        ok = provider.send_email(
            to_email="destinatario@test.com",
            subject="Asunto SMTP",
            html_body="<p>Mensaje</p>",
            text_body="Mensaje",
        )
        assert ok is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user@example.com", "secretpassword")
        mock_server.sendmail.assert_called_once()


class TestProductionStartupValidation:
    """Verifica que en producción el servidor falle al arrancar si faltan variables de correo."""

    def test_production_fails_without_email_provider(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "EMAIL_PROVIDER": ""}, clear=False):
            with pytest.raises(RuntimeError, match="EMAIL_PROVIDER debe estar configurada"):
                validate_email_configuration()

    def test_production_fails_with_invalid_email_provider(self):
        with patch.dict(os.environ, {"ENVIRONMENT": "production", "EMAIL_PROVIDER": "fake_mail"}, clear=False):
            with pytest.raises(RuntimeError, match="proveedores transaccionales admitidos"):
                validate_email_configuration()

    def test_production_fails_without_email_from(self):
        with patch.dict(
            os.environ,
            {"ENVIRONMENT": "production", "EMAIL_PROVIDER": "resend", "EMAIL_FROM": ""},
            clear=False,
        ):
            with pytest.raises(RuntimeError, match="EMAIL_FROM debe estar configurada"):
                validate_email_configuration()

    def test_production_fails_without_api_key_for_resend(self):
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "EMAIL_PROVIDER": "resend",
                "EMAIL_FROM": "no-reply@aquareef.app",
                "EMAIL_API_KEY": "",
            },
            clear=False,
        ):
            with pytest.raises(RuntimeError, match="EMAIL_API_KEY es obligatoria"):
                validate_email_configuration()

    def test_production_fails_without_smtp_host(self):
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "EMAIL_PROVIDER": "smtp",
                "EMAIL_FROM": "no-reply@aquareef.app",
                "SMTP_HOST": "",
            },
            clear=False,
        ):
            with pytest.raises(RuntimeError, match="SMTP_HOST es obligatoria"):
                validate_email_configuration()

    def test_production_fails_without_frontend_url(self):
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "EMAIL_PROVIDER": "resend",
                "EMAIL_FROM": "no-reply@aquareef.app",
                "EMAIL_API_KEY": "re_valid_key",
                "FRONTEND_URL": "",
            },
            clear=False,
        ):
            with pytest.raises(RuntimeError, match="FRONTEND_URL es obligatoria"):
                validate_email_configuration()

    def test_production_passes_with_complete_config(self):
        with patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "production",
                "EMAIL_PROVIDER": "resend",
                "EMAIL_FROM": "no-reply@aquareef.app",
                "EMAIL_API_KEY": "re_valid_key",
                "FRONTEND_URL": "https://www.aquareef.app",
            },
            clear=False,
        ):
            assert validate_email_configuration() is True


class TestTransactionalEmailsEndToEnd:
    """Verifica que el registro y el reseteo envíen correos reales (mockeados) sin filtrar tokens en la API."""

    def test_register_sends_verification_email_and_api_never_returns_token(self, setup_mock_email_provider):
        email = "test_register_flow@aquapulse.io"
        with patch.dict(os.environ, {"FRONTEND_URL": "https://app.aquapulse.io"}):
            res = client.post(
                "/api/auth/register",
                json={"email": email, "password": "SecurePassword123!", "full_name": "Test User"},
            )
            assert res.status_code == 201
            data = res.json()

            # La API jamás debe devolver el token de verificación en el cuerpo JSON
            assert "verify_token" not in data
            assert "verify_email_token" not in data
            assert "verify_url" not in data

            # El proveedor en memoria debió recibir exactamente 1 correo
            sent = setup_mock_email_provider.get_sent_emails()
            assert len(sent) == 1
            record = sent[0]
            assert record.to_email == email
            assert "Verifica tu cuenta" in record.subject

            # El cuerpo del correo DEBE contener el enlace con el token
            assert "https://app.aquapulse.io/?verify_email_token=" in record.text_body
            assert "https://app.aquapulse.io/?verify_email_token=" in record.html_body

    def test_forgot_password_sends_reset_email_and_api_never_returns_token(self, setup_mock_email_provider):
        email = "forgot_user_flow@aquapulse.io"
        db = SessionLocal()
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email,
                hashed_password=hash_password("CurrentPassword123!"),
                is_active=True,
                email_verified=True,
            )
            db.add(user)
            db.commit()
        db.close()

        setup_mock_email_provider.clear()

        with patch.dict(os.environ, {"FRONTEND_URL": "https://app.aquapulse.io"}):
            res = client.post("/api/auth/forgot-password", json={"email": email})
            assert res.status_code == 200
            data = res.json()

            # Respuesta neutra sin filtrar datos
            assert data.get("ok") is True
            assert "reset_token" not in data
            assert "reset_url" not in data
            assert "reset_token_dev" not in data
            assert "reset_url_dev" not in data

            # Se envió el correo transaccional
            sent = setup_mock_email_provider.get_sent_emails()
            assert len(sent) == 1
            record = sent[0]
            assert record.to_email == email
            assert "Restablecimiento de contraseña" in record.subject

            # El cuerpo contiene el enlace de reseteo
            assert "https://app.aquapulse.io/?reset_token=" in record.text_body
            assert "https://app.aquapulse.io/?reset_token=" in record.html_body

    def test_resend_verification_endpoint_sends_new_email(self, setup_mock_email_provider):
        email = "unverified_resend@aquapulse.io"
        db = SessionLocal()
        user = db.query(User).filter(User.email == email).first()
        if not user:
            user = User(
                email=email,
                hashed_password=hash_password("Pass123!"),
                is_active=False,
                email_verified=False,
            )
            db.add(user)
            db.commit()
        db.close()

        setup_mock_email_provider.clear()

        with patch.dict(os.environ, {"FRONTEND_URL": "https://app.aquapulse.io"}):
            res = client.post("/api/auth/resend-verification", json={"email": email})
            assert res.status_code == 200
            data = res.json()
            assert data.get("ok") is True

            sent = setup_mock_email_provider.get_sent_emails()
            assert len(sent) == 1
            assert sent[0].to_email == email
            assert "https://app.aquapulse.io/?verify_email_token=" in sent[0].text_body


class TestUnverifiedAccountBehavior:
    """
    Verifica qué puede y qué no puede hacer una cuenta no verificada:
    - Endpoints públicos permitidos: health, profiles, legal, register, forgot-password, verify-email, resend-verification.
    - Endpoints protegidos bloqueados: login (403), tanks (403), measurements (403), auth/me (403).
    - Activación inmediata tras verificar el correo.
    """

    def test_unverified_account_allowed_and_blocked_endpoints(self, setup_mock_email_provider):
        email = "unverified_permissions@aquapulse.io"
        password = "SecurePassword123!"

        # 1. Registrar usuario con REQUIRE_EMAIL_VERIFICATION=true
        with patch.dict(os.environ, {"REQUIRE_EMAIL_VERIFICATION": "true", "FRONTEND_URL": "https://www.aquareef.app"}):
            reg_res = client.post(
                "/api/auth/register",
                json={"email": email, "password": password, "full_name": "Unverified User"},
            )
            assert reg_res.status_code == 201

            # 2. Endpoints que una cuenta sin verificar o visitante SIEMPRE puede usar:
            assert client.get("/api/health").status_code == 200
            assert client.get("/api/marine-profiles").status_code == 200
            assert client.get("/api/legal/privacy").status_code == 200
            assert client.get("/api/legal/terms").status_code == 200
            assert client.post("/api/auth/resend-verification", json={"email": email}).status_code == 200

            # 3. Intentar iniciar sesión: bloqueado con 403 Forbidden
            auth_attempts.clear()
            db_clean = SessionLocal()
            db_clean.query(RateLimitRecord).delete()
            db_clean.commit()
            db_clean.close()

            login_res = client.post("/api/auth/login", json={"email": email, "password": password})
            assert login_res.status_code == 403
            assert "Debes verificar tu correo" in login_res.json().get("detail", "")

            # 4. Intentar usar un token de acceso previo sobre endpoints protegidos:
            db = SessionLocal()
            user = db.query(User).filter(User.email == email).first()
            assert user.email_verified is False
            token = create_access_token({"sub": str(user.id), "email": user.email, "token_version": 1})
            db.close()

            headers = {"Authorization": f"Bearer {token}"}
            me_res = client.get("/api/auth/me", headers=headers)
            assert me_res.status_code == 403
            assert "Debes verificar tu correo" in me_res.json().get("detail", "")

            tanks_res = client.get("/api/tanks", headers=headers)
            assert tanks_res.status_code == 403
            assert "Debes verificar tu correo" in tanks_res.json().get("detail", "")

            # 5. Obtener el token de verificación del correo enviado
            sent = setup_mock_email_provider.get_sent_emails()
            assert len(sent) >= 1
            body = sent[-1].text_body
            match = re.search(r"verify_email_token=([A-Za-z0-9_.\-]+)", body)
            assert match is not None
            verify_token = match.group(1)

            # 6. Activar la cuenta mediante el endpoint de verificación
            verify_res = client.post("/api/auth/verify-email", json={"token": verify_token})
            assert verify_res.status_code == 200
            assert verify_res.json().get("ok") is True

            # 7. Ahora la cuenta está verificada y activa:
            # Login exitoso
            login_ok_res = client.post("/api/auth/login", json={"email": email, "password": password})
            assert login_ok_res.status_code == 200
            new_access_token = login_ok_res.json()["access_token"]
            auth_headers = {"Authorization": f"Bearer {new_access_token}"}

            # Acceso permitido a endpoints protegidos
            me_ok = client.get("/api/auth/me", headers=auth_headers)
            assert me_ok.status_code == 200
            assert me_ok.json()["email"] == email

            tanks_ok = client.get("/api/tanks", headers=auth_headers)
            assert tanks_ok.status_code == 200
            assert isinstance(tanks_ok.json(), list)


class TestNoTokensOrUrlsInLogs:
    """Garantiza que nunca se impriman tokens ni URLs completas en los registros de logging."""

    def test_logs_do_not_contain_tokens_or_full_links(self, caplog):
        caplog.set_level(logging.DEBUG)
        email = "logging_check@aquapulse.io"

        with patch.dict(os.environ, {"FRONTEND_URL": "https://secure.aquapulse.io"}):
            # Registro
            client.post(
                "/api/auth/register",
                json={"email": email, "password": "Password123!", "full_name": "Log Tester"},
            )
            # Solicitud de reseteo
            client.post("/api/auth/forgot-password", json={"email": email})

        all_logs = caplog.text
        # Ningún JWT largo ni enlace con token debe estar en el log
        assert "verify_email_token=" not in all_logs
        assert "reset_token=" not in all_logs
        assert "https://secure.aquapulse.io/?verify_email_token=" not in all_logs
        assert "https://secure.aquapulse.io/?reset_token=" not in all_logs
