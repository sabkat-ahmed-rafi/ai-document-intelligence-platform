from datetime import datetime
from typing import Any
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
    query: str = Field(..., min_length=1, description="Semantic text query to search for")
    limit: int = Field(default=5, ge=1, le=50, description="Max number of similar chunks to retrieve")
    collection_id: str | None = Field(default=None, description="Optional filter to scope search within a collection")
    document_id: str | None = Field(default=None, description="Optional filter to scope search to a single document")


class ChunkSearchResult(BaseModel):
    id: str
    document_id: str
    collection_id: str | None = None
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    similarity: float = Field(..., description="Cosine similarity score between 0.0 and 1.0")
