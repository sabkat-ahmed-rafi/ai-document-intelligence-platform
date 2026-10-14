from core.config import settings

from .client import EmailClient, EmailDelivery, EmailMessage
from .renderer import render_template


class EmailService:

    def __init__(self, client: EmailClient):
        self.client = client

    async def send(self, message: EmailMessage) -> EmailDelivery:
        return await self.client.send(message)

    async def send_password_reset(
        self,
        *,
        recipient: str,
        reset_code: str,
        recipient_name: str | None = None,
        expires_in_minutes: int = 30,
        idempotency_key: str | None = None,
    ) -> EmailDelivery:
        display_name = recipient_name or "there"
        html = render_template(
            "password_reset.html",
            {
                "recipient_name": display_name,
                "reset_code": reset_code,
                "expires_in_minutes": expires_in_minutes,
            },
        )
        text = (
            f"Hi {display_name},\n\n"
            f"Use this code to reset your password: {reset_code}\n\n"
            f"This code expires in {expires_in_minutes} minutes. If you did not "
            "request a password reset, you can ignore this email."
        )
        return await self.send(
            EmailMessage(
                recipients=(recipient,),
                subject="Reset your password",
                html=html,
                text=text,
                idempotency_key=idempotency_key,
            )
        )

    async def send_email_verification(
        self,
        *,
        recipient: str,
        verification_url: str,
        recipient_name: str | None = None,
        expires_in_minutes: int = 60,
        idempotency_key: str | None = None,
    ) -> EmailDelivery:
        display_name = recipient_name or "there"
        html = render_template(
            "email_verification.html",
            {
                "recipient_name": display_name,
                "verification_url": verification_url,
                "expires_in_minutes": expires_in_minutes,
            },
        )
        text = (
            f"Hi {display_name},\n\n"
            f"Thanks for signing up! Please verify your email by visiting:\n"
            f"{verification_url}\n\n"
            f"This link expires in {expires_in_minutes} minutes. If you did not "
            "create an account, you can safely ignore this email."
        )
        return await self.send(
            EmailMessage(
                recipients=(recipient,),
                subject="Verify your email",
                html=html,
                text=text,
                idempotency_key=idempotency_key,
            )
        )
