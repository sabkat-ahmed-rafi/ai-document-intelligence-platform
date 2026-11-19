from fastapi import APIRouter, Depends, status

from modules.auth.dependencies import get_current_active_user
from modules.users.model import Users
from shared.schemas import ApiResponse

from ..dependencies import get_chat_service
from ..schemas import (
    ChatQueryRequest,
    ChatQueryResponse,
    SingleDocumentChatRequest,
)
from ..service import ChatService
from .sse import create_sse_response

router = APIRouter()


@router.post(
    "/chat",
    response_model=ApiResponse[ChatQueryResponse],
    status_code=status.HTTP_200_OK,
    summary="Ask questions across all documents or filtered knowledge bases",
)
async def chat_documents(
    payload: ChatQueryRequest,
    current_user: Users = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Ask a natural language question over your document library using grounded RAG.
    - Set `stream=false` (default) for an instant, complete JSON response with inline [Source N] tags and structured citation cards.
    - Set `stream=true` for real-time word-by-word token streaming via Server-Sent Events (SSE).
    - Optionally scope to a `collection_id` or single `document_id`.
    """
    if payload.stream:
        stream_gen = chat_service.stream_query(
            user_id=current_user.id,
            question=payload.question,
            search_mode=payload.search_mode,
            collection_id=payload.collection_id,
            document_id=payload.document_id,
            top_k=payload.top_k,
            similarity_threshold=payload.similarity_threshold,
        )
        return create_sse_response(stream_gen)

    result = await chat_service.query(
        user_id=current_user.id,
        question=payload.question,
        search_mode=payload.search_mode,
        collection_id=payload.collection_id,
        document_id=payload.document_id,
        top_k=payload.top_k,
        similarity_threshold=payload.similarity_threshold,
    )
    return ApiResponse(
        message="Response generated successfully",
        data=result,
    )


@router.post(
    "/{document_id}/chat",
    response_model=ApiResponse[ChatQueryResponse],
    status_code=status.HTTP_200_OK,
    summary="Ask questions scoped strictly to a single document",
)
async def chat_single_document(
    document_id: str,
    payload: SingleDocumentChatRequest,
    current_user: Users = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Ask a question focused strictly on one specific document.
    Ensures answers are grounded only within the selected document's parsed chunks and pages.
    Supports both batch execution and real-time SSE streaming.
    """
    if payload.stream:
        stream_gen = chat_service.stream_query(
            user_id=current_user.id,
            question=payload.question,
            search_mode=payload.search_mode,
            document_id=document_id,
            top_k=payload.top_k,
            similarity_threshold=payload.similarity_threshold,
        )
        return create_sse_response(stream_gen)

    result = await chat_service.query(
        user_id=current_user.id,
        question=payload.question,
        search_mode=payload.search_mode,
        document_id=document_id,
        top_k=payload.top_k,
        similarity_threshold=payload.similarity_threshold,
    )
    return ApiResponse(
        message="Response generated successfully",
        data=result,
    )
