from core.config import settings

from .client import EmailClient
from .exceptions import EmailConfigurationError
from .providers import GoogleSMTPEmailClient
from .service import EmailService


def get_email_client() -> EmailClient:
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        raise EmailConfigurationError(
            "Google SMTP is not configured. "
            "Please provide SMTP_USER and SMTP_PASSWORD in your .env file."
        )

    sender = settings.EMAIL_FROM or settings.SMTP_USER
    return GoogleSMTPEmailClient(
        host=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        sender=sender,
        use_tls=settings.SMTP_USE_TLS,
    )


def get_email_service() -> EmailService:
    return EmailService(client=get_email_client())
