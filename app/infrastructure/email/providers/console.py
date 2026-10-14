import logging
from ..client import EmailClient, EmailDelivery, EmailMessage

logger = logging.getLogger(__name__)


class ConsoleEmailClient(EmailClient):

    def __init__(self, sender: str = "noreply@example.com"):
        self.sender = sender

    async def send(self, message: EmailMessage) -> EmailDelivery:
        logger.info(
            "\n" + "=" * 55 + "\n"
            "[EMAIL DISPATCHED via Console Provider]\n"
            f"From: {self.sender}\n"
            f"To: {', '.join(message.recipients)}\n"
            f"Subject: {message.subject}\n"
            f"Content:\n{message.text or message.html}\n"
            + "=" * 55 + "\n"
        )
        return EmailDelivery(message_id="mock-console-delivery-id")
