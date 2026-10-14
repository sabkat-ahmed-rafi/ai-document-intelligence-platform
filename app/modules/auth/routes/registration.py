from fastapi import APIRouter, Depends

from shared.schemas import ApiResponse
from modules.users.schemas import UserResponse

from ..dependencies import get_registration_service
from ..schemas import RegisterRequest
from ..services.registration import RegistrationService

router = APIRouter()


@router.post("/register", response_model=ApiResponse[UserResponse])
async def register(
    data: RegisterRequest,
    registration_service: RegistrationService = Depends(get_registration_service),
):
    user = await registration_service.register(data)
    return ApiResponse(
        message="User registered successfully",
        data=user,
    )
