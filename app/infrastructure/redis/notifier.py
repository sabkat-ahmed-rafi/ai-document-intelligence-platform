import json
import logging
from datetime import datetime, timezone
from typing import Any

from .client import get_async_redis_client

logger = logging.getLogger(__name__)


class DocumentProgressNotifier:
    """
    Publishes real-time document processing stage transitions to Redis Pub/Sub channels.
    Allows FastAPI Server-Sent Events (SSE) endpoints to stream live updates to frontends.
    """

    @staticmethod
    def get_document_channel(document_id: str) -> str:
        return f"doc:{document_id}:progress"

    @staticmethod
    def get_user_channel(user_id: str) -> str:
        return f"user:{user_id}:documents"

    async def notify(
        self,
        *,
        document_id: str,
        user_id: str,
        status: str,
        stage: str,
        progress: int,
        message: str,
        total_chunks: int = 0,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Publishes progress payload to document-scoped and user-scoped channels.
        """
        payload = {
            "document_id": document_id,
            "user_id": user_id,
            "status": status,
            "stage": stage,
            "progress": progress,
            "message": message,
            "total_chunks": total_chunks,
            "error_message": error_message,
            "metadata": metadata or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        serialized = json.dumps(payload)
        doc_channel = self.get_document_channel(document_id)
        user_channel = self.get_user_channel(user_id)

        try:
            redis = get_async_redis_client()
            # Publish to both channels
            await redis.publish(doc_channel, serialized)
            await redis.publish(user_channel, serialized)
            logger.debug(f"Published progress event to {doc_channel} ({stage} {progress}%)")
        except Exception as exc:
            logger.warning(
                f"Failed to publish progress notification for document {document_id} to Redis: {exc}"
            )
