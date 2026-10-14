import uuid

from .schemas import UserCreate, UserResponse
from .repository import UserRepository
from .model import Users
from .security import hash_password
from .exceptions import EmailAlreadyExists


class UserService:

    def __init__(self, repository: UserRepository):
        self.repository = repository

    async def create_user(self, data: UserCreate) -> UserResponse:
        existing = await self.repository.get_by_email(data.email)
        if existing:
            raise EmailAlreadyExists()
        user = Users(
            id=str(uuid.uuid4()),
            email=data.email,
            password_hash=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            role=data.role,
            is_active=True,
            is_verified=True,
        )
        created = await self.repository.create(user)
        return UserResponse.model_validate(created)

    async def get_by_email(self, email: str) -> Users | None:
        return await self.repository.get_by_email(email)

    async def get_by_id(self, user_id: str) -> Users | None:
        return await self.repository.get_by_id(user_id)
