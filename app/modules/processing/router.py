from fastapi import APIRouter, Depends, Query, status

from modules.auth.dependencies import get_current_active_user
from modules.users.model import Users
from shared.schemas import ApiResponse

from .dependencies import get_processing_service
from .schemas import (
    ChunkSearchRequest,
    ChunkSearchResult,
    DocumentChunkListResponse,
    DocumentProcessingStatusResponse,
    DocumentSummaryResponse,
)
from .service import ProcessingService
from .tasks import enqueue_document_processing

router = APIRouter()


@router.post(
    "/{document_id}/process",
    response_model=ApiResponse[DocumentProcessingStatusResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger or re-trigger document AI processing via Celery",
)
async def trigger_document_processing(
    document_id: str,
    run_in_background: bool = Query(
        True,
        description="Run asynchronously in Celery worker queue (default: true)",
    ),
    current_user: Users = Depends(get_current_active_user),
    processing_service: ProcessingService = Depends(get_processing_service),
):
    """
    Triggers parsing, layout-aware chunking, vector embedding, and pgvector indexing.
    Can be run asynchronously via distributed Celery workers (HTTP 202) or synchronously (waiting for completion).
    """
    if run_in_background:
        task_id = enqueue_document_processing(
            document_id=document_id,
            user_id=current_user.id,
        )
        return ApiResponse(
            message=f"Document processing queued in Celery worker queue (task_id: {task_id})",
            data=DocumentProcessingStatusResponse(
                document_id=document_id,
                status="queued",
                total_chunks=0,
                error_message=None,
                doc_metadata={"celery_task_id": task_id},
                updated_at=current_user.created_at,
            ),
        )

    # Synchronous execution
    result = await processing_service.process_document(
        document_id=document_id,
        user_id=current_user.id,
    )
    return ApiResponse(
        message=f"Document processing completed with status '{result.status}'",
        data=result,
    )


@router.get(
    "/{document_id}/chunks",
    response_model=ApiResponse[DocumentChunkListResponse],
    summary="Get all parsed chunks for a document",
)
async def get_document_chunks(
    document_id: str,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: Users = Depends(get_current_active_user),
    processing_service: ProcessingService = Depends(get_processing_service),
):
    """Retrieves all parsed text chunks and metadata indexed in Supabase pgvector for a document."""
    result = await processing_service.get_document_chunks(
        document_id=document_id,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    return ApiResponse(
        message="Document chunks retrieved successfully",
        data=result,
    )


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


@router.get(
    "/{document_id}/summary",
    response_model=ApiResponse[DocumentSummaryResponse],
    summary="Get automated executive summary and extracted entities for a document",
)
async def get_document_summary(
    document_id: str,
    current_user: Users = Depends(get_current_active_user),
    processing_service: ProcessingService = Depends(get_processing_service),
):
    """
    Retrieves the executive summary and extracted entity catalog (parties, dates,
    financial values, classification, topics) stored in the document's metadata.
    """
    result = await processing_service.get_document_summary(
        document_id=document_id,
        user_id=current_user.id,
    )
    message = (
        "Document summary retrieved successfully"
        if result.has_summary
        else "No summary available for this document"
    )
    return ApiResponse(
        message=message,
        data=result,
    )


@router.post(
    "/{document_id}/summarize",
    response_model=ApiResponse[DocumentSummaryResponse],
    summary="Generate or re-generate document summary and entities on-demand",
)
async def summarize_document(
    document_id: str,
    current_user: Users = Depends(get_current_active_user),
    processing_service: ProcessingService = Depends(get_processing_service),
):
    """
    Triggers on-demand executive summarization and entity extraction across all parsed chunks
    of this document, persisting the resulting summary to the document metadata.
    """
    result = await processing_service.summarize_document(
        document_id=document_id,
        user_id=current_user.id,
    )
    return ApiResponse(
        message="Document summary generated successfully",
        data=result,
    )
