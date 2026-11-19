import asyncio
import json
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import StreamingResponse

from infrastructure.redis.client import get_async_redis_client
from infrastructure.redis.notifier import DocumentProgressNotifier
from modules.auth.dependencies import get_current_active_user
from modules.documents.dependencies import get_document_repository
from modules.documents.enums import DocumentStatus
from modules.documents.repository import DocumentRepository
from modules.users.model import Users

router = APIRouter()


async def format_sse_stream(
    event_stream: AsyncIterator[dict[str, Any]],
) -> AsyncIterator[str]:
    """Serializes dictionaries into standard W3C Server-Sent Events (SSE) format."""
    async for event in event_stream:
        event_name = event.get("event", "progress")
        payload = json.dumps(event.get("data", {}))
        yield f"event: {event_name}\ndata: {payload}\n\n"


@router.get(
    "/progress/stream",
    summary="Real-time SSE progress stream for all documents belonging to current user",
)
async def stream_user_documents_progress(
    request: Request,
    current_user: Users = Depends(get_current_active_user),
):
    """
    Long-lived Server-Sent Events (SSE) stream broadcasting all document processing
    stage transitions for the authenticated user, allowing multi-document dashboard views
    to update without polling.
    """
    channel_name = DocumentProgressNotifier.get_user_channel(current_user.id)
    redis_client = await get_async_redis_client()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel_name)

    async def event_generator():
        try:
            yield {
                "event": "connected",
                "data": {
                    "user_id": current_user.id,
                    "message": "Subscribed to document updates stream",
                },
            }
            idle_count = 0
            while True:
                if await request.is_disconnected():
                    break

                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("type") == "message":
                    idle_count = 0
                    payload_str = msg.get("data")
                    if isinstance(payload_str, bytes):
                        payload_str = payload_str.decode("utf-8")
                    try:
                        payload = json.loads(payload_str)
                    except Exception:
                        continue

                    yield {
                        "event": "progress",
                        "data": payload,
                    }
                else:
                    idle_count += 1
                    if idle_count >= 15:
                        idle_count = 0
                        yield {
                            "event": "ping",
                            "data": {"timestamp": datetime.now(timezone.utc).isoformat()},
                        }
        except asyncio.CancelledError:
            pass
        finally:
            try:
                await pubsub.unsubscribe(channel_name)
                if hasattr(pubsub, "aclose"):
                    await pubsub.aclose()
                else:
                    await pubsub.close()
            except Exception:
                pass

    return StreamingResponse(
        format_sse_stream(event_generator()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


@router.get(
    "/{document_id}/progress",
    summary="Real-time SSE progress stream for a specific document",
)
async def stream_document_progress(
    document_id: str,
    request: Request,
    current_user: Users = Depends(get_current_active_user),
    doc_repo: DocumentRepository = Depends(get_document_repository),
):
    """
    Server-Sent Events (SSE) stream providing real-time stage-by-stage progress
    (downloading -> parsing -> chunking -> embedding -> summarizing -> completed/failed)
    for a single document. Closes automatically once a terminal state is reached.
    """
    # Verify document exists and belongs to user
    doc = await doc_repo.get_by_id(document_id, user_id=current_user.id)
    if not doc:
        async def not_found_generator():
            yield {
                "event": "error",
                "data": {"error": "Document not found", "document_id": document_id},
            }
        return StreamingResponse(
            format_sse_stream(not_found_generator()),
            media_type="text/event-stream",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    # If already in a terminal state, yield final event and exit immediately
    if doc.status in (DocumentStatus.COMPLETED.value, DocumentStatus.FAILED.value):
        async def terminal_generator():
            yield {
                "event": "progress",
                "data": {
                    "document_id": doc.id,
                    "user_id": current_user.id,
                    "status": doc.status,
                    "stage": doc.status,
                    "progress": 100,
                    "message": f"Document is {doc.status}.",
                    "total_chunks": 0,
                    "error_message": doc.error_message,
                    "metadata": doc.doc_metadata,
                    "is_terminal": True,
                },
            }
        return StreamingResponse(
            format_sse_stream(terminal_generator()),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Content-Type": "text/event-stream; charset=utf-8",
            },
        )

    channel_name = DocumentProgressNotifier.get_document_channel(document_id)
    redis_client = await get_async_redis_client()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel_name)

    async def event_generator():
        try:
            # Re-check document in case it reached terminal state right during subscription
            fresh_doc = await doc_repo.get_by_id(document_id, user_id=current_user.id)
            if fresh_doc and fresh_doc.status in (DocumentStatus.COMPLETED.value, DocumentStatus.FAILED.value):
                yield {
                    "event": "progress",
                    "data": {
                        "document_id": fresh_doc.id,
                        "user_id": current_user.id,
                        "status": fresh_doc.status,
                        "stage": fresh_doc.status,
                        "progress": 100,
                        "message": f"Document is {fresh_doc.status}.",
                        "total_chunks": 0,
                        "error_message": fresh_doc.error_message,
                        "metadata": fresh_doc.doc_metadata,
                        "is_terminal": True,
                    },
                }
                return

            # Yield initial connection confirmation with current document status
            yield {
                "event": "progress",
                "data": {
                    "document_id": document_id,
                    "user_id": current_user.id,
                    "status": fresh_doc.status if fresh_doc else "processing",
                    "stage": "starting",
                    "progress": 10,
                    "message": "Connected to real-time progress stream.",
                    "total_chunks": 0,
                    "error_message": None,
                    "is_terminal": False,
                },
            }

            idle_count = 0
            while True:
                if await request.is_disconnected():
                    break

                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if msg and msg.get("type") == "message":
                    idle_count = 0
                    payload_str = msg.get("data")
                    if isinstance(payload_str, bytes):
                        payload_str = payload_str.decode("utf-8")
                    try:
                        payload = json.loads(payload_str)
                    except Exception:
                        continue

                    is_terminal = payload.get("status") in ("completed", "failed") or payload.get("stage") in ("completed", "failed")
                    payload["is_terminal"] = is_terminal

                    yield {
                        "event": "progress",
                        "data": payload,
                    }

                    if is_terminal:
                        break
                else:
                    idle_count += 1
                    if idle_count >= 15:
                        idle_count = 0
                        yield {
                            "event": "ping",
                            "data": {"timestamp": datetime.now(timezone.utc).isoformat()},
                        }
        except asyncio.CancelledError:
            pass
        finally:
            try:
                await pubsub.unsubscribe(channel_name)
                if hasattr(pubsub, "aclose"):
                    await pubsub.aclose()
                else:
                    await pubsub.close()
            except Exception:
                pass

    return StreamingResponse(
        format_sse_stream(event_generator()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )
