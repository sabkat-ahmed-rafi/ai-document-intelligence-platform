from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.refresh_token import RefreshToken


class RefreshTokenRepository:

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, token: RefreshToken) -> RefreshToken:
        """Store a new refresh token for the user/session without affecting other devices."""
        self.session.add(token)
        await self.session.commit()
        return token

    async def is_valid(
        self,
        token_id: str,
        user_id: str,
        token_hash: str,
        now: datetime,
    ) -> bool:
        result = await self.session.execute(
            select(RefreshToken.id).where(
                RefreshToken.id == token_id,
                RefreshToken.user_id == user_id,
                RefreshToken.token_hash == token_hash,
                RefreshToken.expires_at > now,
            )
        )
        return result.scalar_one_or_none() is not None

    async def delete(
        self,
        token_id: str,
        user_id: str,
        token_hash: str,
    ) -> bool:
        """Delete specific device refresh token on logout."""
        result = await self.session.execute(
            delete(RefreshToken).where(
                RefreshToken.id == token_id,
                RefreshToken.user_id == user_id,
                RefreshToken.token_hash == token_hash,
            )
        )
        await self.session.commit()
        return result.rowcount == 1

    async def delete_all_for_user(self, user_id: str) -> int:
        """Delete all refresh tokens for a user (used on password reset)."""
        result = await self.session.execute(
            delete(RefreshToken).where(RefreshToken.user_id == user_id)
        )
        await self.session.commit()
        return result.rowcount

    async def delete_others_for_user(self, user_id: str, keep_token_id: str | None = None) -> int:
        """Delete all refresh tokens except the current device (used on change password)."""
        stmt = delete(RefreshToken).where(RefreshToken.user_id == user_id)
        if keep_token_id:
            stmt = stmt.where(RefreshToken.id != keep_token_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount

    async def delete_expired_for_user(self, user_id: str, now: datetime) -> int:
        """Delete all expired refresh tokens for a specific user."""
        stmt = delete(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.expires_at <= now,
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount
