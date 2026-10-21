from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database import get_db

from .repository import CollectionRepository
from .service import CollectionService


def get_collection_repository(
    session: AsyncSession = Depends(get_db),
) -> CollectionRepository:
    return CollectionRepository(session)


def get_collection_service(
    repository: CollectionRepository = Depends(get_collection_repository),
) -> CollectionService:
    return CollectionService(repository)
