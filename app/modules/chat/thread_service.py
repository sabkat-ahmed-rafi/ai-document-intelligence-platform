import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

from core.exceptions import AppException, NotFoundException, ValidationException

from .models import ChatMessage, ChatThread
from .repository import ChatMessageRepository, ChatThreadRepository


class ThreadService:
    """
    Manages persistent conversational threads and message history CRUD operations.
    Decoupled from LLM synthesis and vector search execution.
    """

    def __init__(
        self,
        thread_repository: ChatThreadRepository,
        message_repository: ChatMessageRepository,
    ):
        self.thread_repo = thread_repository
        self.msg_repo = message_repository

    async def create_thread(
        self,
        *,
        user_id: str,
        title: str = "New Conversation",
        collection_id: str | None = None,
        document_id: str | None = None,
    ) -> ChatThread:
        clean_title = title.strip() if title else "New Conversation"
        now = datetime.now(timezone.utc)
        thread = ChatThread(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=clean_title,
            collection_id=collection_id,
            document_id=document_id,
            created_at=now,
            updated_at=now,
        )
        return await self.thread_repo.create(thread)

    async def get_thread(
        self,
        thread_id: str,
        user_id: str,
        include_messages: bool = True,
    ) -> ChatThread:
        thread = await self.thread_repo.get_by_id(
            thread_id=thread_id,
            user_id=user_id,
            include_messages=include_messages,
        )
        if not thread:
            raise NotFoundException(f"Chat thread '{thread_id}' not found")
        return thread

    async def list_threads(
        self,
        *,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[tuple[ChatThread, int]], int]:
        return await self.thread_repo.list_for_user(
            user_id=user_id,
            limit=limit,
            offset=offset,
        )

    async def update_thread_title(
        self,
        *,
        thread_id: str,
        user_id: str,
        title: str,
    ) -> ChatThread:
        clean_title = title.strip()
        if not clean_title:
            raise ValidationException("Thread title cannot be empty")

        thread = await self.get_thread(thread_id, user_id=user_id, include_messages=False)
        thread.title = clean_title
        return await self.thread_repo.update(thread)

    async def delete_thread(
        self,
        *,
        thread_id: str,
        user_id: str,
    ) -> None:
        thread = await self.get_thread(thread_id, user_id=user_id, include_messages=False)
        await self.thread_repo.soft_delete(thread)

    async def list_thread_messages(
        self,
        *,
        thread_id: str,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[ChatMessage], int]:
        # Verify user has access to thread
        await self.get_thread(thread_id, user_id=user_id, include_messages=False)
        return await self.msg_repo.list_for_thread(
            thread_id=thread_id,
            limit=limit,
            offset=offset,
        )
