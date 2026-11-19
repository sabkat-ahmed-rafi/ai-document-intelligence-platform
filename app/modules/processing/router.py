from fastapi import APIRouter

from .routes import (
    process_router,
    search_router,
    stream_router,
    summary_router,
)
from .routes.stream import format_sse_stream as _format_sse_stream

# Main aggregated processing router mounted in app.py with prefix="/documents"
router = APIRouter()

# Register sub-routers (fixed routes like /progress/stream and /search mounted before /{document_id}/...)
router.include_router(stream_router)
router.include_router(search_router)
router.include_router(summary_router)
router.include_router(process_router)

__all__ = ["router", "_format_sse_stream"]
