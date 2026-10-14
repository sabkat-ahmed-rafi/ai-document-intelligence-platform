import resend
from resend.exceptions import ResendError

from ..client import EmailClient, EmailDelivery, EmailMessage
from ..exceptions import EmailConfigurationError, EmailDeliveryFailed


class ResendEmailClient(EmailClient):

    def __init__(self, api_key: str, sender: str):
        if not api_key or not sender:
            raise EmailConfigurationError()

        self.sender = sender
        resend.api_key = api_key

    async def send(self, message: EmailMessage) -> EmailDelivery:
        params: resend.Emails.SendParams = {
            "from": self.sender,
            "to": list(message.recipients),
            "subject": message.subject,
            "html": message.html,
        }
        if message.text is not None:
            params["text"] = message.text
        if message.reply_to is not None:
            params["reply_to"] = message.reply_to

        options: resend.Emails.SendOptions | None = None
        if message.idempotency_key is not None:
            options = {"idempotency_key": message.idempotency_key}

        try:
            response = await resend.Emails.send_async(params, options)
        except Exception as exc:
            raise EmailDeliveryFailed(f"Resend email delivery failed: {exc}") from exc

        message_id = response.get("id")
        if not message_id:
            raise EmailDeliveryFailed("Email provider returned no message ID")
        return EmailDelivery(message_id=message_id)
