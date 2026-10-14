from fastapi import APIRouter, Depends, Response

from shared.schemas import ApiResponse
from core.config import settings

from ..dependencies import get_password_reset_service
from ..schemas import (
    ForgotPasswordRequest,
    PasswordResetAuthorization,
    ResetPasswordRequest,
    VerifyPasswordResetCodeRequest,
)
from ..services.password_reset import PasswordResetService

router = APIRouter()


@router.post("/forgot-password", response_model=ApiResponse[None])
@router.post("/forget-password", response_model=ApiResponse[None], include_in_schema=False)
async def forgot_password(
    data: ForgotPasswordRequest,
    password_reset_service: PasswordResetService = Depends(
        get_password_reset_service
    ),
):
    await password_reset_service.request_reset(data)
    return ApiResponse(
        message="If an account exists for this email, a reset code has been sent",
        data=None,
    )


@router.post(
    "/verify-password-reset-code",
    response_model=ApiResponse[PasswordResetAuthorization],
)
async def verify_password_reset_code(
    data: VerifyPasswordResetCodeRequest,
    password_reset_service: PasswordResetService = Depends(
        get_password_reset_service
    ),
):
    authorization = await password_reset_service.verify_code(data)
    return ApiResponse(
        message="Password reset code verified successfully",
        data=authorization,
    )


@router.post("/reset-password", response_model=ApiResponse[None])
async def reset_password(
    data: ResetPasswordRequest,
    response: Response,
    password_reset_service: PasswordResetService = Depends(
        get_password_reset_service
    ),
):
    await password_reset_service.reset_password(data)
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
        message="Password reset successfully. All sessions have been terminated. Please log in with your new password.",
        data=None,
    )
