from core.config import settings

from .client import EmailClient
from .exceptions import EmailConfigurationError
from .providers import ResendEmailClient, ConsoleEmailClient
from .service import EmailService


def get_email_client() -> EmailClient:
    provider = settings.EMAIL_PROVIDER.lower()

    if provider == "resend":
        if not settings.RESEND_API_KEY:
            raise EmailConfigurationError(
                "RESEND_API_KEY is not configured in settings or .env. "
                "Provide your Resend API key or set EMAIL_PROVIDER=console for local testing."
            )
        return ResendEmailClient(
            api_key=settings.RESEND_API_KEY,
            sender=settings.EMAIL_FROM,
        )

    if provider in ("console", "local", "mock"):
        return ConsoleEmailClient(sender=settings.EMAIL_FROM)

    raise EmailConfigurationError(
        f"Unsupported email provider: '{settings.EMAIL_PROVIDER}'. Supported: 'resend', 'console'"
    )


def get_email_service() -> EmailService:
    return EmailService(client=get_email_client())
