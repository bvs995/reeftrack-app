"""
AquaReef - Servicio Transaccional de Correos Electrónicos (Email Service)
Provee una arquitectura basada en proveedor abstracto (Resend, Brevo, SMTP, Console, Mock)
para el envío seguro de correos transaccionales (verificación de cuenta y restablecimiento de contraseña).
"""
import os
import re
import logging
import smtplib
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Dict, Any

try:
    import requests
except ImportError:
    requests = None

logger = logging.getLogger("aquapulse.email")


def mask_email(email: str) -> str:
    """Oculta parte del correo para registrar eventos de forma segura sin vulnerar privacidad."""
    if not email or "@" not in email:
        return "***"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked_local}@{domain}"


@dataclass
class SentEmailRecord:
    to_email: str
    subject: str
    html_body: str
    text_body: str
    from_email: str


class BaseEmailProvider(ABC):
    """Interfaz abstracta para proveedores de correo transaccional."""

    @abstractmethod
    def send_email(self, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        """Envía un correo transaccional. Retorna True si fue aceptado/enviado exitosamente."""
        pass


class ResendEmailProvider(BaseEmailProvider):
    """Proveedor transaccional para Resend API (https://resend.com)."""

    def __init__(self, api_key: str, from_email: str):
        self.api_key = api_key
        self.from_email = from_email
        self.endpoint = "https://api.resend.com/emails"

    def send_email(self, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        if not self.api_key:
            logger.error(f"Fallo al enviar correo a {mask_email(to_email)}: API key de Resend no está configurada.")
            return False

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "from": self.from_email,
            "to": [to_email],
            "subject": subject,
            "html": html_body,
            "text": text_body,
        }
        try:
            if requests:
                resp = requests.post(self.endpoint, json=payload, headers=headers, timeout=10)
                if resp.status_code in (200, 201):
                    logger.info(f"Correo enviado exitosamente vía Resend a {mask_email(to_email)}")
                    return True
                logger.error(f"Fallo en envío de correo a {mask_email(to_email)} vía Resend (HTTP {resp.status_code}): error del proveedor o clave API inválida.")
                return False
            else:
                import json
                import urllib.request
                import urllib.error
                req = urllib.request.Request(
                    self.endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        if resp.status in (200, 201):
                            logger.info(f"Correo enviado exitosamente vía Resend a {mask_email(to_email)}")
                            return True
                        logger.error(f"Fallo en envío de correo a {mask_email(to_email)} vía Resend (HTTP {resp.status}): error del proveedor.")
                        return False
                except urllib.error.HTTPError as he:
                    logger.error(f"Fallo en envío de correo a {mask_email(to_email)} vía Resend (HTTP {he.code}): clave API inválida o error del proveedor.")
                    return False
        except Exception as e:
            logger.error(f"Error de conexión comunicando con Resend API para {mask_email(to_email)}: {type(e).__name__}")
            return False


class BrevoEmailProvider(BaseEmailProvider):
    """Proveedor transaccional para Brevo / Sendinblue API (https://brevo.com)."""

    def __init__(self, api_key: str, from_email: str):
        self.api_key = api_key
        self.from_email = from_email
        self.endpoint = "https://api.brevo.com/v3/smtp/email"

    def send_email(self, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        if not self.api_key:
            logger.error(f"Fallo al enviar correo a {mask_email(to_email)}: API key de Brevo no está configurada.")
            return False

        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "sender": {"email": self.from_email, "name": "AquaReef"},
            "to": [{"email": to_email}],
            "subject": subject,
            "htmlContent": html_body,
            "textContent": text_body,
        }
        try:
            if requests:
                resp = requests.post(self.endpoint, json=payload, headers=headers, timeout=10)
                if resp.status_code in (200, 201):
                    logger.info(f"Correo enviado exitosamente vía Brevo a {mask_email(to_email)}")
                    return True
                logger.error(f"Fallo en envío de correo a {mask_email(to_email)} vía Brevo (HTTP {resp.status_code}): error del proveedor o clave API inválida.")
                return False
            else:
                import json
                import urllib.request
                import urllib.error
                req = urllib.request.Request(
                    self.endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        if resp.status in (200, 201):
                            logger.info(f"Correo enviado exitosamente vía Brevo a {mask_email(to_email)}")
                            return True
                        logger.error(f"Fallo en envío de correo a {mask_email(to_email)} vía Brevo (HTTP {resp.status}): error del proveedor.")
                        return False
                except urllib.error.HTTPError as he:
                    logger.error(f"Fallo en envío de correo a {mask_email(to_email)} vía Brevo (HTTP {he.code}): clave API inválida o error del proveedor.")
                    return False
        except Exception as e:
            logger.error(f"Error de conexión comunicando con Brevo API para {mask_email(to_email)}: {type(e).__name__}")
            return False


class SMTPEmailProvider(BaseEmailProvider):
    """Proveedor transaccional clásico mediante servidor SMTP."""

    def __init__(
        self,
        host: str,
        port: int = 587,
        user: Optional[str] = None,
        password: Optional[str] = None,
        from_email: str = "no-reply@aquareef.app",
        use_tls: bool = True,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.from_email = from_email
        self.use_tls = use_tls

    def send_email(self, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        if not self.host:
            logger.error(f"Fallo al enviar correo a {mask_email(to_email)}: Servidor SMTP host no configurado.")
            return False
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.from_email
            msg["To"] = to_email

            if text_body:
                msg.attach(MIMEText(text_body, "plain", "utf-8"))
            if html_body:
                msg.attach(MIMEText(html_body, "html", "utf-8"))

            with smtplib.SMTP(self.host, self.port, timeout=10) as server:
                if self.use_tls:
                    server.starttls()
                if self.user and self.password:
                    server.login(self.user, self.password)
                server.sendmail(self.from_email, [to_email], msg.as_string())

            logger.info(f"Correo enviado exitosamente vía SMTP a {mask_email(to_email)}")
            return True
        except Exception as e:
            logger.error(f"Error en servidor SMTP al enviar correo a {mask_email(to_email)}: {type(e).__name__} (fallo de conexión o credenciales inválidas).")
            return False


class MockEmailProvider(BaseEmailProvider):
    """Proveedor en memoria para pruebas automáticas y validaciones de testing."""

    def __init__(self, from_email: str = "no-reply@aquareef.app"):
        self.from_email = from_email
        self.sent_emails: List[SentEmailRecord] = []

    def send_email(self, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        record = SentEmailRecord(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            from_email=self.from_email,
        )
        self.sent_emails.append(record)
        logger.info(f"[MockEmail] Correo interceptado para {mask_email(to_email)} (Asunto: {subject})")
        return True

    def clear(self):
        self.sent_emails.clear()

    def get_sent_emails(self) -> List[SentEmailRecord]:
        return list(self.sent_emails)


class ConsoleEmailProvider(BaseEmailProvider):
    """Proveedor para desarrollo local: imprime visiblemente el correo en terminal y registra evento sin tokens en logs."""

    def __init__(self, from_email: str = "no-reply@aquareef.app"):
        self.from_email = from_email

    def send_email(self, to_email: str, subject: str, html_body: str, text_body: str) -> bool:
        banner = (
            f"\n"
            f"======================== 📧 AQUAPULSE EMAIL (CONSOLE) ========================\n"
            f"Para:      {to_email}\n"
            f"De:        {self.from_email}\n"
            f"Asunto:    {subject}\n"
            f"------------------------------------------------------------------------------\n"
            f"{text_body.strip()}\n"
            f"==============================================================================\n"
        )
        print(banner, flush=True)

        logger.info(
            f"[ConsoleEmail] Notificación generada de forma segura para {mask_email(to_email)} "
            f"(Asunto: {subject}). Los enlaces confidenciales no se muestran en logs de consola."
        )
        return True


# Instancia singleton o sobreescrita de proveedor
_active_provider: Optional[BaseEmailProvider] = None


def set_email_provider(provider: Optional[BaseEmailProvider]):
    """Permite sobrescribir el proveedor de correo activo (útil para tests con MockEmailProvider)."""
    global _active_provider
    _active_provider = provider


def get_email_provider() -> BaseEmailProvider:
    """
    Retorna el proveedor de correo configurado según las variables de entorno.
    Si no se ha inicializado, instancia el correspondiente.
    """
    global _active_provider
    if _active_provider is not None:
        return _active_provider

    provider_name = os.getenv("EMAIL_PROVIDER", "").strip().lower()
    from_email = os.getenv("EMAIL_FROM", "no-reply@aquareef.app").strip()
    api_key = os.getenv("EMAIL_API_KEY", "").strip()

    if provider_name == "resend":
        _active_provider = ResendEmailProvider(api_key=api_key, from_email=from_email)
    elif provider_name == "brevo":
        _active_provider = BrevoEmailProvider(api_key=api_key, from_email=from_email)
    elif provider_name == "smtp":
        host = os.getenv("SMTP_HOST", "")
        port = int(os.getenv("SMTP_PORT", "587"))
        user = os.getenv("SMTP_USER", "")
        password = os.getenv("SMTP_PASSWORD") or api_key
        tls = os.getenv("SMTP_TLS", "true").lower() in ("true", "1", "yes")
        _active_provider = SMTPEmailProvider(
            host=host, port=port, user=user, password=password, from_email=from_email, use_tls=tls
        )
    elif provider_name == "mock":
        _active_provider = MockEmailProvider(from_email=from_email)
    elif provider_name in ("console", ""):
        # Por defecto en desarrollo local: Console
        _active_provider = ConsoleEmailProvider(from_email=from_email)
    else:
        logger.error(
            f"Fallo en configuración de correo: proveedor '{provider_name}' no reconocido. "
            "Se utilizará ConsoleEmailProvider por seguridad."
        )
        _active_provider = ConsoleEmailProvider(from_email=from_email)

    return _active_provider


def check_email_configuration_on_startup() -> bool:
    """
    Verifica la configuración del servicio de correo al arrancar la aplicación.
    - En producción: Si falta configuración crítica, detiene el arranque arrojando RuntimeError.
    - En desarrollo: Emite advertencias y avisos claros en la terminal sobre el estado del proveedor.
    """
    is_prod = os.getenv("ENVIRONMENT", "").strip().lower() == "production"
    if is_prod:
        return validate_email_configuration()

    provider = os.getenv("EMAIL_PROVIDER", "").strip().lower()
    from_email = os.getenv("EMAIL_FROM", "").strip() or "no-reply@aquareef.app"
    api_key = os.getenv("EMAIL_API_KEY", "").strip()
    frontend_url = os.getenv("FRONTEND_URL", "").strip()

    if not provider or provider == "console":
        logger.warning(
            "⚠️  [EMAIL CONFIG] EMAIL_PROVIDER está configurado en modo 'console' o no está definido. "
            "Los correos transaccionales (activación, reseteo) se imprimirán visiblemente en la terminal "
            "y no se enviarán a buzones reales."
        )
    elif provider in ("resend", "brevo"):
        if not api_key:
            logger.error(
                f"🚨 [EMAIL CONFIG] EMAIL_PROVIDER está configurado como '{provider}', pero falta la variable "
                "EMAIL_API_KEY en el entorno. Los envíos de correo fallarán con error."
            )
        else:
            logger.info(f"✅ [EMAIL CONFIG] Proveedor transaccional '{provider}' configurado con remitente {from_email}.")
    elif provider == "smtp":
        host = os.getenv("SMTP_HOST", "").strip()
        if not host:
            logger.error(
                "🚨 [EMAIL CONFIG] EMAIL_PROVIDER está configurado como 'smtp', pero falta la variable "
                "SMTP_HOST en el entorno. Los envíos de correo fallarán con error."
            )
        else:
            logger.info(f"✅ [EMAIL CONFIG] Proveedor SMTP '{host}' configurado con remitente {from_email}.")
    elif provider == "mock":
        logger.info("ℹ️  [EMAIL CONFIG] Proveedor 'mock' en memoria activo (modo pruebas).")
    else:
        logger.error(
            f"🚨 [EMAIL CONFIG] Proveedor EMAIL_PROVIDER='{provider}' desconocido. "
            "Los envíos usarán la consola por defecto."
        )

    if not frontend_url:
        logger.warning(
            "⚠️  [EMAIL CONFIG] Variable FRONTEND_URL no definida. "
            "Se usará 'http://localhost:5173' como base predeterminada para los enlaces."
        )

    return True


def validate_email_configuration() -> bool:
    """
    Valida que en entorno de producción (ENVIRONMENT=production) estén configuradas
    todas las variables necesarias para el envío transaccional de correos.
    Si alguna falta, detiene el arranque del servidor arrojando RuntimeError con mensaje claro.
    """
    is_prod = os.getenv("ENVIRONMENT", "").strip().lower() == "production"
    if not is_prod:
        return True

    provider = os.getenv("EMAIL_PROVIDER", "").strip().lower()
    allowed_providers = ("resend", "brevo", "smtp")

    if not provider or provider not in allowed_providers:
        critical_msg = (
            "🚨 ERROR CRÍTICO DE CONFIGURACIÓN EN PRODUCCIÓN: La variable EMAIL_PROVIDER debe estar configurada "
            f"con uno de los proveedores transaccionales admitidos: {allowed_providers}.\n"
            "AquaReef se niega a arrancar en producción sin un proveedor de correo transaccional activo "
            "para garantizar la verificación de cuentas y el restablecimiento seguro de contraseñas."
        )
        logger.critical(critical_msg)
        raise RuntimeError(critical_msg)

    from_email = os.getenv("EMAIL_FROM", "").strip()
    if not from_email or "@" not in from_email:
        critical_msg = (
            "🚨 ERROR CRÍTICO DE CONFIGURACIÓN EN PRODUCCIÓN: La variable EMAIL_FROM debe estar configurada "
            "con una dirección de correo válida para el remitente (ej. no-reply@aquareef.app)."
        )
        logger.critical(critical_msg)
        raise RuntimeError(critical_msg)

    if provider in ("resend", "brevo"):
        api_key = os.getenv("EMAIL_API_KEY", "").strip()
        if not api_key:
            critical_msg = (
                f"🚨 ERROR CRÍTICO DE CONFIGURACIÓN EN PRODUCCIÓN: La variable EMAIL_API_KEY es obligatoria "
                f"cuando se utiliza el proveedor transaccional '{provider}'."
            )
            logger.critical(critical_msg)
            raise RuntimeError(critical_msg)

    elif provider == "smtp":
        host = os.getenv("SMTP_HOST", "").strip()
        if not host:
            critical_msg = (
                "🚨 ERROR CRÍTICO DE CONFIGURACIÓN EN PRODUCCIÓN: La variable SMTP_HOST es obligatoria "
                "cuando se utiliza el proveedor transaccional 'smtp'."
            )
            logger.critical(critical_msg)
            raise RuntimeError(critical_msg)

    frontend_url = os.getenv("FRONTEND_URL", "").strip()
    if not frontend_url or not (frontend_url.startswith("http://") or frontend_url.startswith("https://")):
        critical_msg = (
            "🚨 ERROR CRÍTICO DE CONFIGURACIÓN EN PRODUCCIÓN: La variable FRONTEND_URL es obligatoria "
            "y debe contener una URL absoluta (ej. https://www.aquareef.app) para generar los enlaces seguros de correo."
        )
        logger.critical(critical_msg)
        raise RuntimeError(critical_msg)

    return True


# ==============================================================================
# PLANTILLAS Y FUNCIONES DE ALTO NIVEL PARA ENVÍO
# ==============================================================================

def send_verification_email(to_email: str, verify_url: str) -> bool:
    """
    Envía correo transaccional de verificación de cuenta.
    NUNCA imprime en los logs el token ni el enlace completo.
    """
    subject = "AquaReef - Verifica tu cuenta"

    text_body = (
        f"Hola,\n\n"
        f"¡Gracias por unirte a AquaReef! Para activar tu cuenta y comenzar a monitorear tus acuarios,\n"
        f"por favor confirma tu dirección de correo electrónico ingresando al siguiente enlace seguro:\n\n"
        f"{verify_url}\n\n"
        f"Este enlace expirará en 24 horas.\n"
        f"Si no creaste esta cuenta, puedes desestimar este mensaje con total seguridad.\n\n"
        f"— El equipo de AquaReef"
    )

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 24px;">
      <div style="max-width: 560px; margin: 0 auto; background-color: #1e293b; border-radius: 12px; padding: 32px; border: 1px solid #334155;">
        <h1 style="color: #38bdf8; font-size: 24px; margin-bottom: 16px;">Verifica tu cuenta en AquaReef</h1>
        <p style="font-size: 15px; line-height: 1.6; color: #cbd5e1;">
          ¡Gracias por unirte a AquaReef! Para activar tu cuenta y acceder al panel de control de tus acuarios, confirma tu dirección de correo:
        </p>
        <div style="text-align: center; margin: 32px 0;">
          <a href="{verify_url}" style="background-color: #0284c7; color: #ffffff; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: bold; font-size: 16px; display: inline-block;">
            Activar mi cuenta
          </a>
        </div>
        <p style="font-size: 13px; color: #94a3b8; line-height: 1.5;">
          O copia y pega el siguiente enlace en tu navegador:<br>
          <span style="word-break: break-all; color: #38bdf8;">{verify_url}</span>
        </p>
        <hr style="border: none; border-top: 1px solid #334155; margin: 24px 0;">
        <p style="font-size: 12px; color: #64748b; margin: 0;">
          Este enlace es confidencial y expirará en 24 horas. Si no solicitaste esta cuenta, ignora este correo.
        </p>
      </div>
    </body>
    </html>
    """

    provider = get_email_provider()
    success = provider.send_email(to_email=to_email, subject=subject, html_body=html_body, text_body=text_body)
    if not success:
        logger.error(f"Fallo al enviar correo de verificación a {mask_email(to_email)}: el proveedor no completó el envío.")
    return success


def send_password_reset_email(to_email: str, reset_url: str) -> bool:
    """
    Envía correo transaccional de restablecimiento de contraseña.
    NUNCA imprime en los logs el token ni el enlace completo.
    """
    subject = "AquaReef - Restablecimiento de contraseña"

    text_body = (
        f"Hola,\n\n"
        f"Hemos recibido una solicitud para restablecer la contraseña de tu cuenta en AquaReef.\n"
        f"Por favor ingresa al siguiente enlace seguro para crear tu nueva contraseña:\n\n"
        f"{reset_url}\n\n"
        f"Este enlace es de un solo uso y expirará en 30 minutos.\n"
        f"Si tú no solicitaste este cambio, puedes ignorar este mensaje; tu cuenta permanece segura.\n\n"
        f"— El equipo de AquaReef"
    )

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: Arial, sans-serif; background-color: #0f172a; color: #f8fafc; padding: 24px;">
      <div style="max-width: 560px; margin: 0 auto; background-color: #1e293b; border-radius: 12px; padding: 32px; border: 1px solid #334155;">
        <h1 style="color: #38bdf8; font-size: 24px; margin-bottom: 16px;">Restablecer contraseña</h1>
        <p style="font-size: 15px; line-height: 1.6; color: #cbd5e1;">
          Hemos recibido una solicitud para restablecer la contraseña de tu cuenta en AquaReef. Haz clic en el botón siguiente para definir una nueva contraseña:
        </p>
        <div style="text-align: center; margin: 32px 0;">
          <a href="{reset_url}" style="background-color: #0284c7; color: #ffffff; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: bold; font-size: 16px; display: inline-block;">
            Restablecer Contraseña
          </a>
        </div>
        <p style="font-size: 13px; color: #94a3b8; line-height: 1.5;">
          O copia y pega el siguiente enlace en tu navegador:<br>
          <span style="word-break: break-all; color: #38bdf8;">{reset_url}</span>
        </p>
        <hr style="border: none; border-top: 1px solid #334155; margin: 24px 0;">
        <p style="font-size: 12px; color: #64748b; margin: 0;">
          Este enlace es de un solo uso y expirará en 30 minutos. Si no realizaste esta solicitud, desestima este mensaje.
        </p>
      </div>
    </body>
    </html>
    """

    provider = get_email_provider()
    success = provider.send_email(to_email=to_email, subject=subject, html_body=html_body, text_body=text_body)
    if not success:
        logger.error(f"Fallo al enviar correo de restablecimiento de contraseña a {mask_email(to_email)}: el proveedor no completó el envío.")
    return success
