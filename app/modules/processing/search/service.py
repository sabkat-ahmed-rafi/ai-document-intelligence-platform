from typing import Any
from langchain_core.embeddings import Embeddings

from core.exceptions import ValidationException

from ..repository import DocumentChunkRepository
from ..schemas import ChunkSearchResult


class ChunkSearchService:
    """
    Dedicated search service for document chunks across vector, keyword, and hybrid modes.
    Encapsulates FastEmbed embedding generation, pgvector similarity, and Reciprocal Rank Fusion.
    """

    def __init__(
        self,
        chunk_repository: DocumentChunkRepository,
        embeddings: Embeddings,
    ):
        self.chunk_repo = chunk_repository
        self.embeddings = embeddings

    async def search(
        self,
        *,
        user_id: str,
        query: str,
        mode: str = "hybrid",
        collection_id: str | None = None,
        document_id: str | None = None,
        limit: int = 5,
        similarity_threshold: float = 0.0,
    ) -> list[ChunkSearchResult]:
        clean_query = query.strip()
        if not clean_query:
            raise ValidationException("Search query cannot be empty")

        resolved_mode = mode.lower() if mode else "hybrid"

        # 1. Pure Keyword / BM25 Search
        if resolved_mode == "keyword":
            results = await self.chunk_repo.search_keywords(
                query_text=clean_query,
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
                    search_mode="keyword",
                )
                for chunk, score in results
            ]

        # 2. Pure Vector Search (Cosine Similarity via pgvector)
        if resolved_mode == "vector":
            query_vector = await self.embeddings.aembed_query(clean_query)
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
                    search_mode="vector",
                )
                for chunk, score in results
                if score >= similarity_threshold
            ]

        # 3. Hybrid Search (Vector + BM25 via Reciprocal Rank Fusion)
        query_vector = await self.embeddings.aembed_query(clean_query)
        fused_matches = await self.chunk_repo.search_hybrid(
            query_vector=query_vector,
            query_text=clean_query,
            user_id=user_id,
            collection_id=collection_id,
            document_id=document_id,
            limit=limit,
        )

        output: list[ChunkSearchResult] = []
        for fused in fused_matches:
            if similarity_threshold > 0.0 and fused.vector_similarity is not None:
                if fused.vector_similarity < similarity_threshold:
                    continue
            output.append(
                ChunkSearchResult(
                    id=fused.chunk.id,
                    document_id=fused.chunk.document_id,
                    collection_id=fused.chunk.collection_id,
                    content=fused.chunk.content,
                    metadata=fused.chunk.chunk_metadata,
                    similarity=fused.rrf_score,
                    search_mode="hybrid",
                    vector_rank=fused.vector_rank,
                    keyword_rank=fused.keyword_rank,
                    rrf_score=fused.rrf_score,
                )
            )
        return output
