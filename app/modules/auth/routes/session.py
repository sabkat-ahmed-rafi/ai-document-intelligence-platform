from fastapi import APIRouter, Cookie, Depends, Response
from fastapi.security import HTTPAuthorizationCredentials

from shared.schemas import ApiResponse
from modules.users.schemas import UserResponse
from modules.users.model import Users

from ..dependencies import (
    get_session_service,
    verify_refresh_token,
    get_current_active_user,
    security,
)
from ..schemas import AccessToken, ChangePasswordRequest, LoginRequest, LoginResponse, RefreshTokenRequest
from ..security import (
    decode_refresh_token,
)
from ..services.session import SessionService
from core.config import settings

router = APIRouter()


@router.post("/login", response_model=ApiResponse[LoginResponse])
async def login(
    data: LoginRequest,
    response: Response,
    session_service: SessionService = Depends(get_session_service),
):
    result = await session_service.login(data)
    # Set cookies for web browsers
    response.set_cookie(
        key="access_token",
        value=result.token.access_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.set_cookie(
        key="refresh_token",
        value=result.token.refresh_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )
    # Returns tokens in body as well for mobile apps / SPA state
    return ApiResponse(
        message="Login successful",
        data=result,
    )


@router.post("/refresh-token", response_model=ApiResponse[AccessToken])
@router.post("/refresh", response_model=ApiResponse[AccessToken], include_in_schema=False)
async def refresh_access_token(
    response: Response,
    verified_token: tuple[str, dict] = Depends(verify_refresh_token),
    session_service: SessionService = Depends(get_session_service),
):
    raw_token, payload = verified_token
    access_token = await session_service.refresh_access_token(raw_token, payload)
    response.set_cookie(
        key="access_token",
        value=access_token.access_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    return ApiResponse(
        message="Access token refreshed successfully",
        data=access_token,
    )


@router.post("/logout", response_model=ApiResponse[None])
async def logout(
    response: Response,
    verified_token: tuple[str, dict] = Depends(verify_refresh_token),
    session_service: SessionService = Depends(get_session_service),
):
    raw_token, payload = verified_token
    await session_service.logout(raw_token, payload)
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
    )
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=not settings.DEBUG,
        samesite="strict",
    )
    return ApiResponse(
        message="Logout successful",
        data=None,
    )


@router.get("/me", response_model=ApiResponse[UserResponse])
async def get_current_user_profile(
    user: Users = Depends(get_current_active_user),
):
    return ApiResponse(
        message="User profile fetched successfully",
        data=UserResponse.model_validate(user),
    )


@router.post("/change-password", response_model=ApiResponse[None])
async def change_password(
    data: ChangePasswordRequest,
    user: Users = Depends(get_current_active_user),
    refresh_token: str | None = Cookie(default=None),
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    session_service: SessionService = Depends(get_session_service),
):
    # Try to identify the current device's refresh token so this session stays active
    current_token_id = None
    token_str = refresh_token or (credentials.credentials if credentials else None)
    if token_str:
        try:
            payload = decode_refresh_token(token_str)
            current_token_id = payload.get("jti")
        except Exception:
            pass

    await session_service.change_password(
        user=user,
        data=data,
        current_token_id=current_token_id,
    )
    return ApiResponse(
        message="Password changed successfully. Other sessions have been signed out.",
        data=None,
    )
