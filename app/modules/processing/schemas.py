from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, Field


class DocumentChunkResponse(BaseModel):
    id: str
    document_id: str
    collection_id: str | None = None
    chunk_index: int
    content: str
    token_count: int | None = None
    char_count: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class DocumentChunkListResponse(BaseModel):
    document_id: str
    total_chunks: int
    chunks: list[DocumentChunkResponse]


class DocumentProcessingStatusResponse(BaseModel):
    document_id: str
    status: str
    total_chunks: int
    error_message: str | None = None
    doc_metadata: dict[str, Any] | None = None
    updated_at: datetime


class ChunkSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Text query to search for")
    mode: Literal["hybrid", "vector", "keyword"] = Field(
        default="hybrid",
        description="Search algorithm: 'hybrid' (Vector + BM25 via RRF), 'vector' (cosine only), 'keyword' (BM25 only)",
    )
    limit: int = Field(default=5, ge=1, le=50, description="Max number of chunks to retrieve")
    collection_id: str | None = Field(default=None, description="Optional filter to scope search within a collection")
    document_id: str | None = Field(default=None, description="Optional filter to scope search to a single document")
    similarity_threshold: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum score threshold (applied to vector similarity)",
    )


class ChunkSearchResult(BaseModel):
    id: str
    document_id: str
    collection_id: str | None = None
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    similarity: float = Field(
        ...,
        description="Primary relevance score (cosine similarity for vector, BM25 rank for keyword, or RRF score for hybrid)",
    )
    search_mode: str = Field(
        default="vector",
        description="Search algorithm used to produce this result: 'hybrid', 'vector', or 'keyword'",
    )
    vector_rank: int | None = Field(
        default=None,
        description="1-indexed rank from vector search (hybrid search only)",
    )
    keyword_rank: int | None = Field(
        default=None,
        description="1-indexed rank from full-text keyword search (hybrid search only)",
    )
    rrf_score: float | None = Field(
        default=None,
        description="Blended Reciprocal Rank Fusion score (hybrid search only)",
    )
