import uuid
from typing import TYPE_CHECKING
from fastapi import UploadFile

from core.exceptions import NotFoundException, ValidationException
from modules.files.enums import FileCategory, OwnerType
from modules.files.models import File
from modules.files.service import FileService

from .enums import DocumentStatus
from .models import Document
from .repository import DocumentRepository
from .schemas import (
    DocumentBatchUploadResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentUploadResponse,
    FailedDocumentUpload,
)

if TYPE_CHECKING:
    from modules.collections.service import CollectionService


class DocumentService:
    def __init__(
        self,
        repository: DocumentRepository,
        file_service: FileService,
        collection_service: "CollectionService | None" = None,
    ):
        self.repository = repository
        self.file_service = file_service
        self.collection_service = collection_service

    async def upload_document(
        self,
        *,
        file: UploadFile,
        user_id: str,
        title: str | None = None,
        collection_id: str | None = None,
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
            collection_id=collection_id,
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
            collection_id=saved_doc.collection_id,
            status=saved_doc.status,
            filename=saved_doc.original_filename,
            mime_type=saved_doc.mime_type,
            file_size=saved_doc.file_size,
            created_at=saved_doc.created_at,
        )

    async def upload_documents(
        self,
        *,
        files: list[UploadFile],
        user_id: str,
        title: str | None = None,
        collection_id: str | None = None,
        collection_name: str | None = None,
    ) -> DocumentBatchUploadResponse:
        if not files:
            raise ValidationException("At least one file must be provided for upload")

        resolved_collection_id = collection_id

        # Resolve or auto-create collection if collection_name is provided
        if collection_name and collection_name.strip() and self.collection_service:
            collection = await self.collection_service.get_or_create_by_name(
                name=collection_name.strip(),
                user_id=user_id,
            )
            resolved_collection_id = collection.id
        elif resolved_collection_id and self.collection_service:
            # Verify existing collection belongs to user
            await self.collection_service.get_collection(resolved_collection_id, user_id)

        # =========================================================================
        # PHASE 1: ATOMIC PRE-VALIDATION (All-or-Nothing)
        # Read and validate EVERY file (size, empty check, MIME type, extension)
        # before saving any file in storage or database.
        # If ANY file fails, abort immediately; NO files are saved.
        # =========================================================================
        prepared_files: list[dict] = []
        validation_errors: list[str] = []

        for idx, f in enumerate(files, start=1):
            fname = f.filename or f"file_{idx}"
            content = await f.read()
            size = len(content)

            try:
                resolved_content_type = self.file_service.validator.validate(
                    content_type=f.content_type or "application/octet-stream",
                    size=size,
                    category=FileCategory.DOCUMENT,
                    filename=f.filename,
                )
                prepared_files.append({
                    "file": f,
                    "content": content,
                    "content_type": resolved_content_type,
                    "size": size,
                    "filename": fname,
                })
            except Exception as exc:
                err_msg = str(getattr(exc, "message", str(exc)))
                validation_errors.append(f"'{fname}': {err_msg}")

        if validation_errors:
            # Rejection: Zero files saved to storage, zero records in database
            raise ValidationException(
                f"Batch upload rejected. {len(validation_errors)} file(s) failed validation; no files were saved: "
                + " | ".join(validation_errors)
            )

        # =========================================================================
        # PHASE 2: INGESTION & STORAGE (All files are pre-validated)
        # Only reached when 100% of the files in the batch passed Phase 1.
        # If an unexpected storage failure occurs halfway, roll back stored files.
        # =========================================================================
        is_single = len(prepared_files) == 1
        uploaded: list[DocumentUploadResponse] = []
        uploaded_file_records: list[File] = []

        try:
            for item in prepared_files:
                f = item["file"]
                doc_title = title if (is_single and title) else item["filename"]

                # 1. Upload file using FileService
                file_record = await self.file_service.upload(
                    file=f,
                    owner_type=OwnerType.DOCUMENT,
                    owner_id=user_id,
                    category=FileCategory.DOCUMENT,
                    content=item["content"],
                    resolved_content_type=item["content_type"],
                )
                uploaded_file_records.append(file_record)

                # 2. Create the Document entity in PostgreSQL with PENDING status
                document = Document(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    collection_id=resolved_collection_id,
                    file_id=file_record.id,
                    title=doc_title,
                    original_filename=file_record.original_name,
                    mime_type=file_record.mime_type,
                    file_size=file_record.size,
                    status=DocumentStatus.PENDING.value,
                    error_message=None,
                    doc_metadata=None,
                )
                saved_doc = await self.repository.create(document)

                uploaded.append(
                    DocumentUploadResponse(
                        document_id=saved_doc.id,
                        collection_id=saved_doc.collection_id,
                        status=saved_doc.status,
                        filename=saved_doc.original_filename,
                        mime_type=saved_doc.mime_type,
                        file_size=saved_doc.file_size,
                        created_at=saved_doc.created_at,
                    )
                )

        except Exception as exc:
            # Rollback: Clean up any files that were already saved in cloud storage during this batch
            for rec in uploaded_file_records:
                try:
                    await self.file_service.storage.delete(rec.storage_key)
                except Exception:
                    pass
            raise exc

        primary_doc_id = uploaded[0].document_id if uploaded else None

        return DocumentBatchUploadResponse(
            collection_id=resolved_collection_id,
            uploaded=uploaded,
            failed=[],
            total_uploaded=len(uploaded),
            total_failed=0,
            document_id=primary_doc_id,
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
            collection_id=doc.collection_id,
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
        collection_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> DocumentListResponse:
        docs, total = await self.repository.list_for_user(
            user_id=user_id,
            collection_id=collection_id,
            limit=limit,
            offset=offset,
        )
        items = [
            DocumentDetailResponse(
                id=d.id,
                user_id=d.user_id,
                collection_id=d.collection_id,
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
