import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse

from modules.auth.dependencies import get_current_active_user
from modules.users.model import Users
from shared.schemas import ApiResponse

from .dependencies import get_chat_service
from .schemas import (
    ChatMessageResponse,
    ChatQueryRequest,
    ChatQueryResponse,
    SingleDocumentChatRequest,
    ThreadChatRequest,
    ThreadChatResponse,
    ThreadCreateRequest,
    ThreadDetailResponse,
    ThreadListResponse,
    ThreadResponse,
    ThreadUpdateRequest,
)
from .service import ChatService

router = APIRouter()
threads_router = APIRouter()


async def _format_sse_stream(
    event_stream: AsyncIterator[dict[str, Any]],
) -> AsyncIterator[str]:
    """
    Serializes application dictionary events into standard W3C Server-Sent Events (SSE) format:
    event: <event_name>\n
    data: <json_string>\n\n
    """
    async for event in event_stream:
        event_name = event.get("event", "message")
        payload = json.dumps(event.get("data", {}))
        yield f"event: {event_name}\ndata: {payload}\n\n"


def _create_sse_response(
    event_stream: AsyncIterator[dict[str, Any]],
) -> StreamingResponse:
    """Wraps an asynchronous generator in a StreamingResponse with appropriate anti-buffering headers."""
    return StreamingResponse(
        _format_sse_stream(event_stream),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


# =========================================================================
# Stateless Document Chat Routes (Prefix: /documents)
# =========================================================================


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
        return _create_sse_response(stream_gen)

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
        return _create_sse_response(stream_gen)

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


# =========================================================================
# Conversational Memory & Chat Thread Routes (Prefix: /threads)
# =========================================================================


@threads_router.post(
    "",
    response_model=ApiResponse[ThreadResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation thread",
)
async def create_thread(
    payload: ThreadCreateRequest,
    current_user: Users = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Creates a persistent conversation thread optionally scoped to a collection or document.
    """
    thread = await chat_service.create_thread(
        user_id=current_user.id,
        title=payload.title,
        collection_id=payload.collection_id,
        document_id=payload.document_id,
    )
    return ApiResponse(
        message="Conversation thread created successfully",
        data=ThreadResponse(
            id=thread.id,
            user_id=thread.user_id,
            title=thread.title,
            collection_id=thread.collection_id,
            document_id=thread.document_id,
            message_count=0,
            created_at=thread.created_at,
            updated_at=thread.updated_at,
        ),
    )


@threads_router.get(
    "",
    response_model=ApiResponse[ThreadListResponse],
    status_code=status.HTTP_200_OK,
    summary="List user conversation threads",
)
async def list_threads(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: Users = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Returns a paginated list of conversation threads for the current authenticated user.
    """
    threads_with_count, total = await chat_service.list_threads(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    items = [
        ThreadResponse(
            id=t.id,
            user_id=t.user_id,
            title=t.title,
            collection_id=t.collection_id,
            document_id=t.document_id,
            message_count=count,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t, count in threads_with_count
    ]
    return ApiResponse(
        message="Threads retrieved successfully",
        data=ThreadListResponse(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        ),
    )


@threads_router.get(
    "/{thread_id}",
    response_model=ApiResponse[ThreadDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="Get conversation thread details with message history",
)
async def get_thread_detail(
    thread_id: str,
    current_user: Users = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Retrieves full details of a specific thread including all historical messages.
    """
    thread = await chat_service.get_thread(
        thread_id=thread_id,
        user_id=current_user.id,
        include_messages=True,
    )
    messages = [ChatMessageResponse.model_validate(m) for m in thread.messages]
    return ApiResponse(
        message="Thread retrieved successfully",
        data=ThreadDetailResponse(
            id=thread.id,
            user_id=thread.user_id,
            title=thread.title,
            collection_id=thread.collection_id,
            document_id=thread.document_id,
            created_at=thread.created_at,
            updated_at=thread.updated_at,
            messages=messages,
        ),
    )


@threads_router.patch(
    "/{thread_id}",
    response_model=ApiResponse[ThreadResponse],
    status_code=status.HTTP_200_OK,
    summary="Rename conversation thread",
)
async def update_thread_title(
    thread_id: str,
    payload: ThreadUpdateRequest,
    current_user: Users = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Updates the title of an existing conversation thread.
    """
    thread = await chat_service.update_thread_title(
        thread_id=thread_id,
        user_id=current_user.id,
        title=payload.title,
    )
    return ApiResponse(
        message="Thread updated successfully",
        data=ThreadResponse(
            id=thread.id,
            user_id=thread.user_id,
            title=thread.title,
            collection_id=thread.collection_id,
            document_id=thread.document_id,
            message_count=len(thread.messages) if hasattr(thread, "messages") and thread.messages else 0,
            created_at=thread.created_at,
            updated_at=thread.updated_at,
        ),
    )


@threads_router.delete(
    "/{thread_id}",
    response_model=ApiResponse[None],
    status_code=status.HTTP_200_OK,
    summary="Delete conversation thread",
)
async def delete_thread(
    thread_id: str,
    current_user: Users = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Soft-deletes a conversation thread and archives its message history.
    """
    await chat_service.delete_thread(thread_id=thread_id, user_id=current_user.id)
    return ApiResponse(
        message="Thread deleted successfully",
        data=None,
    )


@threads_router.post(
    "/{thread_id}/chat",
    response_model=ApiResponse[ThreadChatResponse],
    status_code=status.HTTP_200_OK,
    summary="Send a message in a conversation thread with multi-turn memory",
)
async def chat_in_thread(
    thread_id: str,
    payload: ThreadChatRequest,
    current_user: Users = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Send a message within an existing conversational thread.
    - Uses prior conversation turns to contextualize follow-up questions.
    - Searches documents using hybrid search and passes grounded context to LLM.
    - Automatically persists both user and assistant messages with source citations.
    - Set `stream=true` for token-by-token real-time streaming via Server-Sent Events (SSE).
    """
    if payload.stream:
        stream_gen = chat_service.stream_thread_query(
            thread_id=thread_id,
            user_id=current_user.id,
            message=payload.message,
            search_mode=payload.search_mode,
            top_k=payload.top_k,
            similarity_threshold=payload.similarity_threshold,
        )
        return _create_sse_response(stream_gen)

    result = await chat_service.thread_query(
        thread_id=thread_id,
        user_id=current_user.id,
        message=payload.message,
        search_mode=payload.search_mode,
        top_k=payload.top_k,
        similarity_threshold=payload.similarity_threshold,
    )
    return ApiResponse(
        message="Message processed successfully",
        data=result,
    )


@threads_router.get(
    "/{thread_id}/messages",
    response_model=ApiResponse[list[ChatMessageResponse]],
    status_code=status.HTTP_200_OK,
    summary="List paginated messages in a conversation thread",
)
async def list_thread_messages(
    thread_id: str,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: Users = Depends(get_current_active_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """
    Fetches paginated chronological messages for a conversation thread.
    """
    messages, _ = await chat_service.list_thread_messages(
        thread_id=thread_id,
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )
    return ApiResponse(
        message="Messages retrieved successfully",
        data=[ChatMessageResponse.model_validate(m) for m in messages],
    )
