import uuid
from fastapi import UploadFile

from core.exceptions import NotFoundException
from modules.files.enums import FileCategory, OwnerType
from modules.files.service import FileService

from .enums import DocumentStatus
from .models import Document
from .repository import DocumentRepository
from .schemas import (
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentUploadResponse,
)


class DocumentService:
    def __init__(
        self,
        repository: DocumentRepository,
        file_service: FileService,
    ):
        self.repository = repository
        self.file_service = file_service

    async def upload_document(
        self,
        *,
        file: UploadFile,
        user_id: str,
        title: str | None = None,
    ) -> DocumentUploadResponse:
        original_name = file.filename or "uploaded_document"
        document_title = title.strip() if title and title.strip() else original_name

        # 1. Upload file using FileService (handles storage upload, size/type validation, file record in DB)
        file_record = await self.file_service.upload(
            file=file,
            owner_type=OwnerType.DOCUMENT,
            owner_id=user_id,
            category=FileCategory.DOCUMENT,
        )

        # 2. Create the Document entity in PostgreSQL with initial PENDING status
        document = Document(
            id=str(uuid.uuid4()),
            user_id=user_id,
            file_id=file_record.id,
            title=document_title,
            original_filename=file_record.original_name,
            mime_type=file_record.mime_type,
            file_size=file_record.size,
            status=DocumentStatus.PENDING.value,
            error_message=None,
            doc_metadata=None,
        )
        saved_doc = await self.repository.create(document)

        return DocumentUploadResponse(
            document_id=saved_doc.id,
            status=saved_doc.status,
            filename=saved_doc.original_filename,
            mime_type=saved_doc.mime_type,
            file_size=saved_doc.file_size,
            created_at=saved_doc.created_at,
        )

    async def get_document(
        self,
        document_id: str,
        user_id: str,
    ) -> DocumentDetailResponse:
        doc = await self.repository.get_by_id(document_id, user_id=user_id)
        if not doc:
            raise NotFoundException("Document not found")

        # Resolve download URL from storage provider (signed or direct URL)
        download_url = None
        try:
            file_record = await self.file_service.get(doc.file_id)
            if hasattr(self.file_service.storage, "get_signed_url"):
                download_url = await self.file_service.storage.get_signed_url(file_record.storage_key)
            else:
                download_url = self.file_service.get_url(file_record)
        except Exception:
            pass

        return DocumentDetailResponse(
            id=doc.id,
            user_id=doc.user_id,
            file_id=doc.file_id,
            title=doc.title,
            original_filename=doc.original_filename,
            mime_type=doc.mime_type,
            file_size=doc.file_size,
            status=doc.status,
            error_message=doc.error_message,
            doc_metadata=doc.doc_metadata,
            download_url=download_url,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )

    async def list_documents(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> DocumentListResponse:
        docs, total = await self.repository.list_for_user(
            user_id=user_id,
            limit=limit,
            offset=offset,
        )
        items = [
            DocumentDetailResponse(
                id=d.id,
                user_id=d.user_id,
                file_id=d.file_id,
                title=d.title,
                original_filename=d.original_filename,
                mime_type=d.mime_type,
                file_size=d.file_size,
                status=d.status,
                error_message=d.error_message,
                doc_metadata=d.doc_metadata,
                download_url=None,
                created_at=d.created_at,
                updated_at=d.updated_at,
            )
            for d in docs
        ]
        return DocumentListResponse(documents=items, total=total)
