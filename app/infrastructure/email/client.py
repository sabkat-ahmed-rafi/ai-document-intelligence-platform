from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EmailMessage:
    recipients: tuple[str, ...]
    subject: str
    html: str
    text: str | None = None
    reply_to: str | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True, slots=True)
class EmailDelivery:
    message_id: str


class EmailClient(ABC):

    @abstractmethod
    async def send(self, message: EmailMessage) -> EmailDelivery:
        """Send an email and return the provider's message identifier."""
        ...
