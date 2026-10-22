import asyncio
import logging

from core.celery_app import celery_app
from infrastructure.database.session import async_session_factory
from infrastructure.storage.factory import get_storage
from modules.documents.repository import DocumentRepository
from modules.files.naming import FileNamer
from modules.files.paths import FilePath
from modules.files.repository import FileRepository
from modules.files.service import FileService
from modules.files.validators import FileValidator

from .chunkers.hybrid_chunker import HybridDocumentChunker
from .embeddings.factory import EmbeddingFactory
from .parsers.docling_parser import DoclingDocumentParser
from .pipeline import DocumentProcessingPipeline
from .repository import DocumentChunkRepository
from .service import ProcessingService
from .vectorstore.supabase_store import SupabaseVectorStoreAdapter

logger = logging.getLogger(__name__)


async def _run_document_processing(document_id: str, user_id: str) -> dict:
    """Internal async executor running in an isolated session."""
    logger.info(f"Starting Celery document processing for document: {document_id}")
    async with async_session_factory() as session:
        doc_repo = DocumentRepository(session)
        chunk_repo = DocumentChunkRepository(session)
        file_repo = FileRepository(session)
        storage = get_storage()

        file_service = FileService(
            repository=file_repo,
            storage=storage,
            validator=FileValidator(),
            namer=FileNamer(),
            path_generator=FilePath(),
        )

        embeddings = EmbeddingFactory.get_embeddings()
        parser = DoclingDocumentParser()
        chunker = HybridDocumentChunker()
        vector_store = SupabaseVectorStoreAdapter(
            repository=chunk_repo,
            embeddings=embeddings,
        )

        pipeline = DocumentProcessingPipeline(
            parser=parser,
            chunker=chunker,
            vector_store=vector_store,
        )

        service = ProcessingService(
            document_repository=doc_repo,
            chunk_repository=chunk_repo,
            file_service=file_service,
            pipeline=pipeline,
        )

        status_res = await service.process_document(
            document_id=document_id,
            user_id=user_id,
        )
        logger.info(
            f"Finished Celery document processing for document: {document_id}. "
            f"Status: {status_res.status}, Chunks: {status_res.total_chunks}"
        )
        return {
            "document_id": document_id,
            "status": status_res.status,
            "total_chunks": status_res.total_chunks,
            "error_message": status_res.error_message,
        }


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="modules.processing.tasks.process_document_task",
)
def process_document_task(self, document_id: str, user_id: str) -> dict:
    """
    Production Celery worker task for distributed asynchronous document intelligence processing.
    Runs inside a dedicated Celery worker process isolated from the web server.
    """
    try:
        return asyncio.run(_run_document_processing(document_id=document_id, user_id=user_id))
    except Exception as exc:
        logger.error(
            f"Celery task failed for document {document_id}: {exc}. Retrying...",
            exc_info=True,
        )
        raise self.retry(exc=exc)


def enqueue_document_processing(document_id: str, user_id: str) -> str | None:
    """
    Enqueues the document processing task into the Celery distributed queue.
    Returns the Celery task ID.
    """
    result = process_document_task.delay(document_id=document_id, user_id=user_id)
    return result.id
