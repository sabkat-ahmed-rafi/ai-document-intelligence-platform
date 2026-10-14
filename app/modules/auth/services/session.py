from datetime import datetime, timezone

from modules.users.model import Users
from modules.users.repository import UserRepository
from modules.users.schemas import UserResponse
from modules.users.security import hash_password, verify_password
from modules.users.service import UserService

from ..exceptions import InactiveUser, InvalidCredentials, InvalidCurrentPassword
from ..models.refresh_token import RefreshToken
from ..repositories.refresh_token import RefreshTokenRepository
from ..schemas import AccessToken, ChangePasswordRequest, LoginRequest, LoginResponse, Token
from ..security import (
    create_refresh_token,
    encode_access_token,
    hash_refresh_token,
)


class SessionService:

    def __init__(
        self,
        user_service: UserService,
        refresh_token_repository: RefreshTokenRepository,
        user_repository: UserRepository,
    ):
        self.user_service = user_service
        self.refresh_token_repository = refresh_token_repository
        self.user_repository = user_repository

    async def login(self, data: LoginRequest) -> LoginResponse:
        user = await self.user_service.get_by_email(data.email)
        if not user or not user.password_hash or not verify_password(data.password, user.password_hash):
            raise InvalidCredentials()
        if not user.is_active:
            raise InactiveUser()

        token = await self._create_token(user.id)
        return LoginResponse(
            user=UserResponse.model_validate(user),
            token=token,
        )

    async def _create_token(self, user_id: str) -> Token:
        refresh_token, token_id, expires_at = create_refresh_token(user_id)
        token_record = RefreshToken(
            id=token_id,
            user_id=user_id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=expires_at,
        )
        # Store refresh token for this specific device/session without wiping others
        await self.refresh_token_repository.create(token_record)

        return Token(
            access_token=encode_access_token(user_id),
            refresh_token=refresh_token,
        )

    async def refresh_access_token(self, token: str, payload: dict) -> AccessToken:
        user_id = payload["sub"]
        user = await self.user_service.get_by_id(user_id)
        if not user:
            raise InvalidCredentials()
        if not user.is_active:
            raise InactiveUser()

        is_valid = await self.refresh_token_repository.is_valid(
            token_id=payload["jti"],
            user_id=user.id,
            token_hash=hash_refresh_token(token),
            now=datetime.now(timezone.utc),
        )
        if not is_valid:
            raise InvalidCredentials("Invalid or expired refresh token")

        return AccessToken(access_token=encode_access_token(user.id))

    async def logout(self, token: str, payload: dict) -> None:
        deleted = await self.refresh_token_repository.delete(
            token_id=payload["jti"],
            user_id=payload["sub"],
            token_hash=hash_refresh_token(token),
        )
        if not deleted:
            raise InvalidCredentials("Invalid or expired refresh token")

    async def change_password(
        self,
        user: Users,
        data: ChangePasswordRequest,
        current_token_id: str | None = None,
    ) -> None:
        if not user.password_hash or not verify_password(data.current_password, user.password_hash):
            raise InvalidCurrentPassword()

        # Update password
        user.password_hash = hash_password(data.new_password)
        await self.user_repository.update(user)

        # Invalidate all OTHER refresh tokens to secure account across devices,
        # but keep the current device logged in for a smooth experience.
        await self.refresh_token_repository.delete_others_for_user(
            user_id=user.id,
            keep_token_id=current_token_id,
        )
