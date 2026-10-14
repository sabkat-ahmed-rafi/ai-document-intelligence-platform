from fastapi import Cookie, Depends, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from infrastructure.database import get_db
from infrastructure.email import EmailService, get_email_service
from .repositories.password_reset import PasswordResetRepository
from .repositories.refresh_token import RefreshTokenRepository
from .security import decode_access_token, decode_refresh_token
from .services.password_reset import PasswordResetService
from .services.registration import RegistrationService
from .services.session import SessionService
from .exceptions import InactiveUser, InvalidCredentials
from modules.users.service import UserService
from modules.users.repository import UserRepository
from modules.users.dependencies import get_user_service, get_user_repository
from modules.users.model import Users

security = HTTPBearer(auto_error=False)


def get_registration_service(
    user_service: UserService = Depends(get_user_service),
):
    return RegistrationService(user_service=user_service)


def get_session_service(
    user_service: UserService = Depends(get_user_service),
    user_repository: UserRepository = Depends(get_user_repository),
    session: AsyncSession = Depends(get_db),
):
    return SessionService(
        user_service=user_service,
        refresh_token_repository=RefreshTokenRepository(session),
        user_repository=user_repository,
    )


def get_password_reset_service(
    user_service: UserService = Depends(get_user_service),
    session: AsyncSession = Depends(get_db),
    email_service: EmailService = Depends(get_email_service),
):
    return PasswordResetService(
        user_service=user_service,
        repository=PasswordResetRepository(session),
        email_service=email_service,
    )


async def verify_api_key(
    x_api_key: str = Header(alias="X-API-Key", default=""),
):
    if not settings.API_KEY or x_api_key != settings.API_KEY:
        raise InvalidCredentials("Invalid or missing API key")
    return True


async def verify_token(
    access_token: str | None = Cookie(default=None),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    token = access_token or (credentials.credentials if credentials else None)
    if not token:
        raise InvalidCredentials("Missing access token")
    return decode_access_token(token)


async def verify_refresh_token(
    request: Request,
    refresh_token: str | None = Cookie(default=None),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> tuple[str, dict]:
    # 1. Try cookie
    token = refresh_token
    # 2. Try Bearer header
    if not token and credentials:
        token = credentials.credentials
    # 3. Try JSON body (for mobile apps or clients not sending cookies/headers)
    if not token and request.headers.get("content-type", "").startswith("application/json"):
        try:
            body = await request.json()
            if isinstance(body, dict):
                token = body.get("refresh_token")
        except Exception:
            pass

    if not token:
        raise InvalidCredentials("Missing refresh token")

    payload = decode_refresh_token(token)
    return token, payload


async def get_current_user(
    token: dict = Depends(verify_token),
    user_service: UserService = Depends(get_user_service),
) -> Users:
    user = await user_service.get_by_id(token["sub"])
    if not user:
        raise InvalidCredentials("User not found")
    return user


async def get_current_active_user(
    user: Users = Depends(get_current_user),
) -> Users:
    if not user.is_active or user.is_deleted:
        raise InactiveUser()
    return user
