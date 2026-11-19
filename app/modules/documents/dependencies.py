from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database import get_db
from modules.files.dependencies import get_file_service
from modules.files.service import FileService
from modules.collections.dependencies import get_collection_service
from modules.collections.service import CollectionService
from modules.processing.repository import DocumentChunkRepository

from .repository import DocumentRepository
from .service import DocumentService


def get_document_repository(
    session: AsyncSession = Depends(get_db),
) -> DocumentRepository:
    return DocumentRepository(session)


def get_document_service(
    repository: DocumentRepository = Depends(get_document_repository),
    file_service: FileService = Depends(get_file_service),
    collection_service: CollectionService = Depends(get_collection_service),
    session: AsyncSession = Depends(get_db),
) -> DocumentService:
    chunk_repository = DocumentChunkRepository(session)
    return DocumentService(
        repository=repository,
        file_service=file_service,
        collection_service=collection_service,
        chunk_repository=chunk_repository,
    )
