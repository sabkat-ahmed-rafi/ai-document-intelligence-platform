import logging
from email.message import EmailMessage as MIMEEmailMessage
from email.utils import formatdate, make_msgid

import aiosmtplib
from aiosmtplib.errors import (
    SMTPAuthenticationError,
    SMTPConnectError,
    SMTPException,
    SMTPTimeoutError,
)

from ..client import EmailClient, EmailDelivery, EmailMessage
from ..exceptions import EmailConfigurationError, EmailDeliveryFailed

logger = logging.getLogger(__name__)


class GoogleSMTPEmailClient(EmailClient):
    """Async SMTP email client configured for Google SMTP (Gmail) and compatible SMTP relays."""

    def __init__(
        self,
        *,
        username: str,
        password: str,
        host: str = "smtp.gmail.com",
        port: int = 587,
        sender: str | None = None,
        use_tls: bool = True,
        timeout: int = 30,
    ):
        if not username or not password:
            raise EmailConfigurationError(
                "Google SMTP username and password are required. "
                "Ensure SMTP_USER and SMTP_PASSWORD are configured in your .env."
            )

        self.host = host
        self.port = port
        self.username = username
        self.password = password.strip().replace(" ", "")  # Strip whitespace from 16-char app password
        self.sender = sender or username
        self.use_tls = use_tls
        self.timeout = timeout

    async def send(self, message: EmailMessage) -> EmailDelivery:
        # Domain for Message-ID header
        domain = "gmail.com"
        if "@" in self.username:
            domain = self.username.split("@")[-1]

        msg_id = make_msgid(domain=domain)

        # Build MIME message
        mime_msg = MIMEEmailMessage()
        mime_msg["From"] = self.sender
        mime_msg["To"] = ", ".join(message.recipients)
        mime_msg["Subject"] = message.subject
        mime_msg["Date"] = formatdate(localtime=True)
        mime_msg["Message-ID"] = msg_id

        if message.reply_to:
            mime_msg["Reply-To"] = message.reply_to

        # Fallback plain text part
        text_content = message.text or "This message contains HTML content."
        mime_msg.set_content(text_content)

        # HTML part
        if message.html:
            mime_msg.add_alternative(message.html, subtype="html")

        # Port 465 uses SSL directly (use_tls=True)
        # Port 587 uses STARTTLS (start_tls=True)
        is_ssl = (self.port == 465)
        use_starttls = (not is_ssl) if self.use_tls else False

        try:
            await aiosmtplib.send(
                mime_msg,
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                use_tls=is_ssl,
                start_tls=use_starttls,
                timeout=self.timeout,
            )
        except SMTPAuthenticationError as exc:
            logger.error("Google SMTP authentication failed for user %s: %s", self.username, exc)
            raise EmailDeliveryFailed(
                "Google SMTP authentication failed. Ensure 2-Step Verification is active "
                "and you are using a 16-character Google App Password (not your account password)."
            ) from exc
        except (SMTPConnectError, SMTPTimeoutError) as exc:
            logger.error("Failed to connect to SMTP server %s:%s: %s", self.host, self.port, exc)
            raise EmailDeliveryFailed(
                f"Failed to connect to SMTP server at {self.host}:{self.port}."
            ) from exc
        except SMTPException as exc:
            logger.error("SMTP error while delivering email: %s", exc)
            raise EmailDeliveryFailed(f"SMTP delivery error: {exc}") from exc
        except Exception as exc:
            logger.error("Unexpected error during email delivery: %s", exc)
            raise EmailDeliveryFailed(f"Unexpected email delivery failure: {exc}") from exc

        return EmailDelivery(message_id=msg_id)
