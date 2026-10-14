import logging
import uuid
from datetime import datetime, timedelta, timezone

from core.exceptions import ValidationException
from infrastructure.email import EmailService
from infrastructure.email.exceptions import EmailDeliveryFailed
from modules.users.security import hash_password
from modules.users.service import UserService

from ..exceptions import InvalidPasswordReset
from ..models.password_reset_code import PasswordResetCode
from ..repositories.password_reset import PasswordResetRepository
from ..schemas import (
    ForgotPasswordRequest,
    PasswordResetAuthorization,
    ResetPasswordRequest,
    VerifyPasswordResetCodeRequest,
)
from ..security import (
    PASSWORD_RESET_CODE_EXPIRE_MINUTES,
    PASSWORD_RESET_MAX_ATTEMPTS,
    PASSWORD_RESET_RESEND_COOLDOWN_SECONDS,
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES,
    create_password_reset_code,
    create_password_reset_token,
    hash_password_reset_code,
    hash_password_reset_token,
    verify_password_reset_code,
)

logger = logging.getLogger(__name__)


class PasswordResetService:

    def __init__(
        self,
        user_service: UserService,
        repository: PasswordResetRepository,
        email_service: EmailService,
    ):
        self.user_service = user_service
        self.repository = repository
        self.email_service = email_service

    async def request_reset(self, data: ForgotPasswordRequest) -> None:
        user = await self.user_service.get_by_email(str(data.email))
        if not user or not user.is_active or user.is_deleted:
            return

        now = datetime.now(timezone.utc)
        existing = await self.repository.get_for_user(user.id)
        cooldown_started_at = now - timedelta(
            seconds=PASSWORD_RESET_RESEND_COOLDOWN_SECONDS
        )
        if existing and existing.requested_at > cooldown_started_at:
            return

        request_id = str(uuid.uuid4())
        code = create_password_reset_code()
        request = PasswordResetCode(
            id=request_id,
            user_id=user.id,
            code_hash=hash_password_reset_code(request_id, code),
            expires_at=now + timedelta(minutes=PASSWORD_RESET_CODE_EXPIRE_MINUTES),
            requested_at=now,
            failed_attempts=0,
        )
        await self.repository.replace_for_user(request)

        # Send password reset email via configured email service
        try:
            await self.email_service.send_password_reset(
                recipient=user.email,
                recipient_name=user.first_name,
                reset_code=code,
                expires_in_minutes=PASSWORD_RESET_CODE_EXPIRE_MINUTES,
                idempotency_key=f"password-reset/{request_id}",
            )
        except EmailDeliveryFailed:
            await self.repository.delete_request(request_id)
            raise

    async def verify_code(
        self,
        data: VerifyPasswordResetCodeRequest,
    ) -> PasswordResetAuthorization:
        user = await self.user_service.get_by_email(str(data.email))
        if not user or not user.is_active or user.is_deleted:
            raise InvalidPasswordReset()

        request = await self.repository.get_for_user(user.id)
        now = datetime.now(timezone.utc)
        if (
            not request
            or request.expires_at <= now
            or request.verified_at is not None
            or request.failed_attempts >= PASSWORD_RESET_MAX_ATTEMPTS
        ):
            raise InvalidPasswordReset()

        if not verify_password_reset_code(request.id, data.code, request.code_hash):
            await self.repository.record_failed_attempt(
                request_id=request.id,
                now=now,
                max_attempts=PASSWORD_RESET_MAX_ATTEMPTS,
            )
            raise InvalidPasswordReset()

        reset_token, reset_token_hash = create_password_reset_token()
        reset_token_expires_at = now + timedelta(
            minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
        )
        verified = await self.repository.mark_verified(
            request_id=request.id,
            code_hash=request.code_hash,
            now=now,
            max_attempts=PASSWORD_RESET_MAX_ATTEMPTS,
            reset_token_hash=reset_token_hash,
            reset_token_expires_at=reset_token_expires_at,
        )
        if not verified:
            raise InvalidPasswordReset()

        return PasswordResetAuthorization(
            reset_token=reset_token,
            expires_in_seconds=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def reset_password(self, data: ResetPasswordRequest) -> None:
        if len(data.new_password.encode("utf-8")) > 72:
            raise ValidationException("Password must not exceed 72 bytes")

        now = datetime.now(timezone.utc)
        token_hash = hash_password_reset_token(data.reset_token)
        request = await self.repository.get_by_reset_token_hash(token_hash, now)
        if not request:
            raise InvalidPasswordReset()

        # Complete reset and delete all refresh tokens to terminate all active sessions
        completed = await self.repository.complete_password_reset(
            request_id=request.id,
            user_id=request.user_id,
            token_hash=token_hash,
            now=now,
            password_hash=hash_password(data.new_password),
        )
        if not completed:
            raise InvalidPasswordReset()
