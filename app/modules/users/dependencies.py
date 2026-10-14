from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database import get_db
from .repository import UserRepository
from .service import UserService


def get_user_repository(
    session: AsyncSession = Depends(get_db),
):
    return UserRepository(session)


def get_user_service(
    repository: UserRepository = Depends(get_user_repository),
):
    return UserService(repository=repository)
