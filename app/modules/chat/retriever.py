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
        search_mode: str = "hybrid",
        collection_id: str | None = None,
        document_id: str | None = None,
        top_k: int = 5,
        similarity_threshold: float = 0.0,
    ) -> RAGContext:
        """
        Retrieves context chunks using hybrid, vector, or keyword search,
        and resolves metadata for context injection.
        """
        clean_query = query.strip()
        if not clean_query:
            raise ValidationException("Search query cannot be empty")

        resolved_mode = search_mode.lower() if search_mode else "hybrid"

        if resolved_mode == "keyword":
            raw_results = await self.chunk_repo.search_keywords(
                query_text=clean_query,
                user_id=user_id,
                collection_id=collection_id,
                document_id=document_id,
                limit=top_k,
            )
        elif resolved_mode == "vector":
            query_vector = await self.embeddings.aembed_query(clean_query)
            raw_results = await self.chunk_repo.search_similar(
                query_vector=query_vector,
                user_id=user_id,
                collection_id=collection_id,
                document_id=document_id,
                limit=top_k,
            )
        else:
            # Default: Hybrid Search (Vector + BM25 via Reciprocal Rank Fusion)
            query_vector = await self.embeddings.aembed_query(clean_query)
            fused_matches = await self.chunk_repo.search_hybrid(
                query_vector=query_vector,
                query_text=clean_query,
                user_id=user_id,
                collection_id=collection_id,
                document_id=document_id,
                limit=top_k,
            )
            raw_results = [(f.chunk, f.rrf_score) for f in fused_matches]

        # Filter by similarity threshold if specified
        if similarity_threshold > 0.0:
            filtered_results = [
                (chunk, score)
                for chunk, score in raw_results
                if score >= similarity_threshold
            ]
        else:
            filtered_results = raw_results

        if not filtered_results:
            return RAGContext(
                formatted_context="",
                citations=[],
                total_sources=0,
                is_empty=True,
            )

        # Batch resolve document titles for human-friendly citations
        doc_ids = list({chunk.document_id for chunk, _ in filtered_results})
        doc_map = await self.doc_repo.get_by_ids(doc_ids, user_id=user_id)
        document_titles = {
            d_id: (doc.title or doc.original_filename)
            for d_id, doc in doc_map.items()
        }

        # Build structured RAGContext
        return RAGContextBuilder.build(
            chunks_with_scores=filtered_results,
            document_titles=document_titles,
        )
