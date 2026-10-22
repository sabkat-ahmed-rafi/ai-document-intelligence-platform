from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from infrastructure.database import get_db
from modules.documents.dependencies import get_document_repository
from modules.documents.repository import DocumentRepository
from modules.files.dependencies import get_file_service
from modules.files.service import FileService

from .chunkers.hybrid_chunker import HybridDocumentChunker
from .embeddings.factory import EmbeddingFactory
from .parsers.docling_parser import DoclingDocumentParser
from .pipeline import DocumentProcessingPipeline
from .repository import DocumentChunkRepository
from .service import ProcessingService
from .vectorstore.supabase_store import SupabaseVectorStoreAdapter


def get_chunk_repository(
    session: AsyncSession = Depends(get_db),
) -> DocumentChunkRepository:
    return DocumentChunkRepository(session)


def get_processing_pipeline(
    chunk_repository: DocumentChunkRepository = Depends(get_chunk_repository),
) -> DocumentProcessingPipeline:
    embeddings = EmbeddingFactory.get_embeddings()
    parser = DoclingDocumentParser()
    chunker = HybridDocumentChunker()
    vector_store = SupabaseVectorStoreAdapter(
        repository=chunk_repository,
        embeddings=embeddings,
    )
    return DocumentProcessingPipeline(
        parser=parser,
        chunker=chunker,
        vector_store=vector_store,
    )


def get_processing_service(
    document_repository: DocumentRepository = Depends(get_document_repository),
    chunk_repository: DocumentChunkRepository = Depends(get_chunk_repository),
    file_service: FileService = Depends(get_file_service),
    pipeline: DocumentProcessingPipeline = Depends(get_processing_pipeline),
) -> ProcessingService:
    return ProcessingService(
        document_repository=document_repository,
        chunk_repository=chunk_repository,
        file_service=file_service,
        pipeline=pipeline,
    )
