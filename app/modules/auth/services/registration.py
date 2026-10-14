from modules.users.schemas import UserCreate, UserResponse
from modules.users.service import UserService
from ..schemas import RegisterRequest


class RegistrationService:

    def __init__(self, user_service: UserService):
        self.user_service = user_service

    async def register(self, data: RegisterRequest) -> UserResponse:
        user = await self.user_service.create_user(
            UserCreate(
                email=data.email,
                password=data.password,
                first_name=data.first_name,
                last_name=data.last_name,
            )
        )
        return user
