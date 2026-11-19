import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi.responses import StreamingResponse


async def format_sse_stream(
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


def create_sse_response(
    event_stream: AsyncIterator[dict[str, Any]],
) -> StreamingResponse:
    """Wraps an asynchronous generator in a StreamingResponse with appropriate anti-buffering headers."""
    return StreamingResponse(
        format_sse_stream(event_stream),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )
