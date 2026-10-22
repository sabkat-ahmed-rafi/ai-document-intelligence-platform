import time
from pathlib import Path
from langchain_core.documents import Document as LCDocument

from core.config import settings
from .chunkers.base import BaseChunker
from .models import DocumentChunk
from .parsers.base import BaseDocumentParser
from .vectorstore.supabase_store import SupabaseVectorStoreAdapter


class DocumentProcessingPipeline:
    """
    Expert-level LangChain Document Processing Pipeline.
    Orchestrates parsing (Docling), layout-aware chunking, vector embedding (FastEmbed),
    and vector indexing in Supabase pgvector.
    """

    def __init__(
        self,
        parser: BaseDocumentParser,
        chunker: BaseChunker,
        vector_store: SupabaseVectorStoreAdapter,
    ):
        self.parser = parser
        self.chunker = chunker
        self.vector_store = vector_store

    async def execute(
        self,
        file_path: str | Path,
        *,
        document_id: str,
        user_id: str,
        collection_id: str | None = None,
        original_filename: str | None = None,
        mime_type: str | None = None,
    ) -> tuple[list[DocumentChunk], dict]:
        """
        Executes end-to-end processing:
        1. Parse file via Docling (extract layout, markdown tables, headings)
        2. Chunk via HybridChunker (respecting tables, headers, and token limits)
        3. Embed & index via SupabaseVectorStoreAdapter (FastEmbed + pgvector)
        Returns the saved DocumentChunk records and processing performance metrics.
        """
        start_time = time.perf_counter()

        # Step 1: Parse using Docling
        parse_start = time.perf_counter()
        raw_docs: list[LCDocument] = await self.parser.parse(
            file_path,
            original_filename=original_filename,
            mime_type=mime_type,
        )
        parse_duration = time.perf_counter() - parse_start

        # Step 2: Layout-aware chunking
        chunk_start = time.perf_counter()
        chunks: list[LCDocument] = self.chunker.chunk(
            raw_docs,
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )
        chunk_duration = time.perf_counter() - chunk_start

        # Step 3: Embed and store in Supabase pgvector
        embed_start = time.perf_counter()
        saved_chunks = await self.vector_store.add_documents(
            documents=chunks,
            document_id=document_id,
            user_id=user_id,
            collection_id=collection_id,
        )
        embed_duration = time.perf_counter() - embed_start

        total_duration = time.perf_counter() - start_time

        metrics = {
            "parser": "docling",
            "chunker": "hybrid",
            "embedding_provider": settings.EMBEDDING_PROVIDER,
            "embedding_model": settings.EMBEDDING_MODEL,
            "total_chunks": len(saved_chunks),
            "parse_duration_seconds": round(parse_duration, 3),
            "chunk_duration_seconds": round(chunk_duration, 3),
            "embed_duration_seconds": round(embed_duration, 3),
            "total_duration_seconds": round(total_duration, 3),
        }

        return saved_chunks, metrics
