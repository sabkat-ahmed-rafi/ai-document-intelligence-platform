from langchain_core.embeddings import Embeddings

from core.exceptions import ValidationException
from modules.documents.repository import DocumentRepository
from modules.processing.repository import DocumentChunkRepository
from .context import RAGContextBuilder
from .schemas import RAGContext


class RAGRetriever:
    """
    Retrieves the most semantically relevant document chunks from Supabase pgvector,
    filters by tenant ownership and optional collection/document boundaries, resolves
    document titles, and compiles a structured RAGContext.
    """

    def __init__(
        self,
        chunk_repository: DocumentChunkRepository,
        document_repository: DocumentRepository,
        embeddings: Embeddings,
    ):
        self.chunk_repo = chunk_repository
        self.doc_repo = document_repository
        self.embeddings = embeddings

    async def retrieve(
        self,
        *,
        user_id: str,
        query: str,
        collection_id: str | None = None,
        document_id: str | None = None,
        top_k: int = 5,
        similarity_threshold: float = 0.0,
    ) -> RAGContext:
        """
        Executes semantic vector search and resolves metadata for context injection.
        """
        clean_query = query.strip()
        if not clean_query:
            raise ValidationException("Search query cannot be empty")

        # 1. Embed query into 384-dim dense vector using FastEmbed
        query_vector = await self.embeddings.aembed_query(clean_query)

        # 2. Query Supabase pgvector using cosine distance <=> operator
        raw_results = await self.chunk_repo.search_similar(
            query_vector=query_vector,
            user_id=user_id,
            collection_id=collection_id,
            document_id=document_id,
            limit=top_k,
        )

        # 3. Apply optional similarity threshold filtering
        filtered_results = [
            (chunk, score)
            for chunk, score in raw_results
            if score >= similarity_threshold
        ]

        if not filtered_results:
            return RAGContext(
                formatted_context="",
                citations=[],
                total_sources=0,
                is_empty=True,
            )

        # 4. Batch resolve document titles for human-friendly citations
        doc_ids = list({chunk.document_id for chunk, _ in filtered_results})
        doc_map = await self.doc_repo.get_by_ids(doc_ids, user_id=user_id)
        document_titles = {
            d_id: (doc.title or doc.original_filename)
            for d_id, doc in doc_map.items()
        }

        # 5. Build structured RAGContext
        return RAGContextBuilder.build(
            chunks_with_scores=filtered_results,
            document_titles=document_titles,
        )
