from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from modules.users.model import Users

from ..models.password_reset_code import PasswordResetCode
from ..models.refresh_token import RefreshToken


class PasswordResetRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_for_user(self, user_id: str) -> PasswordResetCode | None:
        result = await self.session.execute(
            select(PasswordResetCode).where(
                PasswordResetCode.user_id == user_id
            )
        )
        return result.scalar_one_or_none()

    async def replace_for_user(self, request: PasswordResetCode) -> None:
        await self.session.execute(
            delete(PasswordResetCode).where(
                PasswordResetCode.user_id == request.user_id
            )
        )
        self.session.add(request)
        await self.session.commit()

    async def delete_request(self, request_id: str) -> None:
        await self.session.execute(
            delete(PasswordResetCode).where(
                PasswordResetCode.id == request_id
            )
        )
        await self.session.commit()

    async def record_failed_attempt(
        self,
        request_id: str,
        now: datetime,
        max_attempts: int,
    ) -> None:
        await self.session.execute(
            update(PasswordResetCode)
            .where(
                PasswordResetCode.id == request_id,
                PasswordResetCode.verified_at.is_(None),
                PasswordResetCode.expires_at > now,
                PasswordResetCode.failed_attempts < max_attempts,
            )
            .values(failed_attempts=PasswordResetCode.failed_attempts + 1)
        )
        await self.session.commit()

    async def mark_verified(
        self,
        *,
        request_id: str,
        code_hash: str,
        now: datetime,
        max_attempts: int,
        reset_token_hash: str,
        reset_token_expires_at: datetime,
    ) -> bool:
        result = await self.session.execute(
            update(PasswordResetCode)
            .where(
                PasswordResetCode.id == request_id,
                PasswordResetCode.code_hash == code_hash,
                PasswordResetCode.verified_at.is_(None),
                PasswordResetCode.expires_at > now,
                PasswordResetCode.failed_attempts < max_attempts,
            )
            .values(
                verified_at=now,
                reset_token_hash=reset_token_hash,
                reset_token_expires_at=reset_token_expires_at,
            )
        )
        await self.session.commit()
        return result.rowcount == 1

    async def get_by_reset_token_hash(
        self,
        token_hash: str,
        now: datetime,
    ) -> PasswordResetCode | None:
        result = await self.session.execute(
            select(PasswordResetCode).where(
                PasswordResetCode.reset_token_hash == token_hash,
                PasswordResetCode.verified_at.is_not(None),
                PasswordResetCode.reset_token_expires_at > now,
            )
        )
        return result.scalar_one_or_none()

    async def complete_password_reset(
        self,
        *,
        request_id: str,
        user_id: str,
        token_hash: str,
        now: datetime,
        password_hash: str,
    ) -> bool:
        # Consume the one-time authorization before changing credentials so
        # concurrent submissions cannot both reset the password.
        consumed = await self.session.execute(
            delete(PasswordResetCode).where(
                PasswordResetCode.id == request_id,
                PasswordResetCode.user_id == user_id,
                PasswordResetCode.reset_token_hash == token_hash,
                PasswordResetCode.verified_at.is_not(None),
                PasswordResetCode.reset_token_expires_at > now,
            )
        )
        if consumed.rowcount != 1:
            await self.session.rollback()
            return False

        updated = await self.session.execute(
            update(Users)
            .where(
                Users.id == user_id,
                Users.is_active.is_(True),
                Users.deleted_at.is_(None),
            )
            .values(password_hash=password_hash)
        )
        if updated.rowcount != 1:
            await self.session.rollback()
            return False

        await self.session.execute(
            delete(RefreshToken).where(RefreshToken.user_id == user_id)
        )
        await self.session.commit()
        return True
