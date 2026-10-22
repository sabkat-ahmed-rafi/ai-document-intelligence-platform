import os
import tempfile
from pathlib import Path
from typing import Any

from core.exceptions import NotFoundException, ValidationException
from modules.documents.enums import DocumentStatus
from modules.documents.repository import DocumentRepository
from modules.files.service import FileService

from .models import DocumentChunk
from .pipeline import DocumentProcessingPipeline
from .repository import DocumentChunkRepository
from .schemas import (
    ChunkSearchResult,
    DocumentChunkListResponse,
    DocumentChunkResponse,
    DocumentProcessingStatusResponse,
)


class ProcessingService:
    def __init__(
        self,
        document_repository: DocumentRepository,
        chunk_repository: DocumentChunkRepository,
        file_service: FileService,
        pipeline: DocumentProcessingPipeline,
    ):
        self.doc_repo = document_repository
        self.chunk_repo = chunk_repository
        self.file_service = file_service
        self.pipeline = pipeline

    async def process_document(
        self,
        document_id: str,
        user_id: str,
    ) -> DocumentProcessingStatusResponse:
        """
        Processes a document end-to-end:
        Streams from cloud storage -> Docling parsing -> Hybrid chunking -> FastEmbed embedding -> Supabase pgvector.
        Updates document status transitions: pending -> processing -> completed / failed.
        """
        # 1. Fetch document and verify user ownership
        doc = await self.doc_repo.get_by_id(document_id, user_id=user_id)
        if not doc:
            raise NotFoundException("Document not found")

        # 2. Transition state to PROCESSING
        doc.status = DocumentStatus.PROCESSING.value
        doc.error_message = None
        await self.doc_repo.update(doc)

        # 3. Clean up any previous chunks if re-processing
        await self.chunk_repo.delete_by_document_id(doc.id)

        # 4. Resolve file record and download binary from storage
        file_record = await self.file_service.get(doc.file_id)
        file_suffix = Path(doc.original_filename).suffix or ".bin"

        temp_file_path = None
        try:
            # If local storage, we can point directly; if Supabase/S3, download to a temporary file
            if hasattr(self.file_service.storage, "download_bytes"):
                file_bytes = await self.file_service.storage.download_bytes(file_record.storage_key)
            else:
                # Direct download stream or fallback
                import httpx
                # If signed URL is available, fetch bytes
                if hasattr(self.file_service.storage, "get_signed_url"):
                    url = await self.file_service.storage.get_signed_url(file_record.storage_key)
                else:
                    url = self.file_service.get_url(file_record)
                
                async with httpx.AsyncClient() as client:
                    resp = await client.get(url, timeout=60.0)
                    resp.raise_for_status()
                    file_bytes = resp.content

            # Write to a named temporary file with proper extension for Docling
            with tempfile.NamedTemporaryFile(suffix=file_suffix, delete=False) as tmp:
                tmp.write(file_bytes)
                temp_file_path = tmp.name

            # 5. Run the LangChain Processing Pipeline
            saved_chunks, metrics = await self.pipeline.execute(
                temp_file_path,
                document_id=doc.id,
                user_id=user_id,
                collection_id=doc.collection_id,
                original_filename=doc.original_filename,
                mime_type=doc.mime_type,
            )

            # 6. Update document to COMPLETED
            doc.status = DocumentStatus.COMPLETED.value
            doc.doc_metadata = {
                **(doc.doc_metadata or {}),
                "processing": metrics,
            }
            doc.error_message = None
            await self.doc_repo.update(doc)

            return DocumentProcessingStatusResponse(
                document_id=doc.id,
                status=doc.status,
                total_chunks=len(saved_chunks),
                error_message=None,
                doc_metadata=doc.doc_metadata,
                updated_at=doc.updated_at,
            )

        except Exception as exc:
            # Mark document as FAILED and record error message
            error_text = str(getattr(exc, "message", str(exc)))
            doc.status = DocumentStatus.FAILED.value
            doc.error_message = error_text
            await self.doc_repo.update(doc)

            return DocumentProcessingStatusResponse(
                document_id=doc.id,
                status=doc.status,
                total_chunks=0,
                error_message=error_text,
                doc_metadata=doc.doc_metadata,
                updated_at=doc.updated_at,
            )

        finally:
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.remove(temp_file_path)
                except Exception:
                    pass

    async def get_document_chunks(
        self,
        document_id: str,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> DocumentChunkListResponse:
        # Verify document exists and belongs to user
        doc = await self.doc_repo.get_by_id(document_id, user_id=user_id)
        if not doc:
            raise NotFoundException("Document not found")

        chunks, total = await self.chunk_repo.list_by_document_id(
            document_id=document_id,
            limit=limit,
            offset=offset,
        )

        chunk_responses = [
            DocumentChunkResponse(
                id=c.id,
                document_id=c.document_id,
                collection_id=c.collection_id,
                chunk_index=c.chunk_index,
                content=c.content,
                token_count=c.token_count,
                char_count=c.char_count,
                metadata=c.chunk_metadata,
                created_at=c.created_at,
            )
            for c in chunks
        ]

        return DocumentChunkListResponse(
            document_id=document_id,
            total_chunks=total,
            chunks=chunk_responses,
        )

    async def search_chunks(
        self,
        *,
        user_id: str,
        query: str,
        collection_id: str | None = None,
        document_id: str | None = None,
        limit: int = 5,
    ) -> list[ChunkSearchResult]:
        if not query.strip():
            raise ValidationException("Search query cannot be empty")

        query_vector = await self.pipeline.vector_store.embeddings.aembed_query(query)
        results = await self.chunk_repo.search_similar(
            query_vector=query_vector,
            user_id=user_id,
            collection_id=collection_id,
            document_id=document_id,
            limit=limit,
        )

        return [
            ChunkSearchResult(
                id=chunk.id,
                document_id=chunk.document_id,
                collection_id=chunk.collection_id,
                content=chunk.content,
                metadata=chunk.chunk_metadata,
                similarity=round(score, 4),
            )
            for chunk, score in results
        ]
