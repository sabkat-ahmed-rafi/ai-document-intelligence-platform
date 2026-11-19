from fastapi import APIRouter, Depends

from modules.auth.dependencies import get_current_active_user
from modules.users.model import Users
from shared.schemas import ApiResponse

from ..dependencies import get_processing_service
from ..schemas import (
    ChunkSearchRequest,
    ChunkSearchResult,
)
from ..service import ProcessingService

router = APIRouter()


@router.post(
    "/search",
    response_model=ApiResponse[list[ChunkSearchResult]],
    summary="Hybrid, vector, or full-text search across document chunks",
)
async def search_document_chunks(
    data: ChunkSearchRequest,
    current_user: Users = Depends(get_current_active_user),
    processing_service: ProcessingService = Depends(get_processing_service),
):
    """
    Performs high-accuracy search across all documents or scoped to a specific collection/document:
    - `mode="hybrid"` (default): Blends vector cosine similarity and PostgreSQL BM25 full-text search using Reciprocal Rank Fusion (RRF).
    - `mode="vector"`: Pure semantic vector search via pgvector HNSW indexing.
    - `mode="keyword"`: Pure BM25 full-text search using PostgreSQL tsvector and websearch_to_tsquery.
    """
    results = await processing_service.search_chunks(
        user_id=current_user.id,
        query=data.query,
        mode=data.mode,
        collection_id=data.collection_id,
        document_id=data.document_id,
        limit=data.limit,
        similarity_threshold=data.similarity_threshold,
    )
    return ApiResponse(
        message=f"Found {len(results)} matching chunk(s) using {data.mode} search",
        data=results,
    )
