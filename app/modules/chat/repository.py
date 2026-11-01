from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import ChatMessage, ChatThread


class ChatThreadRepository:
    """Handles database persistence and queries for conversation threads."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, thread: ChatThread) -> ChatThread:
        self.session.add(thread)
        await self.session.commit()
        await self.session.refresh(thread)
        return thread

    async def get_by_id(
        self,
        thread_id: str,
        user_id: str,
        include_messages: bool = True,
        include_deleted: bool = False,
    ) -> ChatThread | None:
        stmt = select(ChatThread).where(
            ChatThread.id == thread_id,
            ChatThread.user_id == user_id,
        )
        if not include_deleted:
            stmt = stmt.where(ChatThread.deleted_at.is_(None))

        if include_messages:
            stmt = stmt.options(selectinload(ChatThread.messages))

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[tuple[ChatThread, int]], int]:
        """
        Returns a paginated list of threads with message counts, ordered by most recently updated.
        """
        # Count total active threads
        total_stmt = select(func.count(ChatThread.id)).where(
            ChatThread.user_id == user_id,
            ChatThread.deleted_at.is_(None),
        )
        total = await self.session.scalar(total_stmt) or 0

        # Subquery message count per thread
        msg_count_sub = (
            select(
                ChatMessage.thread_id,
                func.count(ChatMessage.id).label("message_count"),
            )
            .group_by(ChatMessage.thread_id)
            .subquery()
        )

        stmt = (
            select(
                ChatThread,
                func.coalesce(msg_count_sub.c.message_count, 0).label("message_count"),
            )
            .outerjoin(msg_count_sub, ChatThread.id == msg_count_sub.c.thread_id)
            .where(
                ChatThread.user_id == user_id,
                ChatThread.deleted_at.is_(None),
            )
            .order_by(ChatThread.updated_at.desc())
            .offset(offset)
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        threads_with_count = [(row[0], int(row[1])) for row in result.all()]
        return threads_with_count, total

    async def update(self, thread: ChatThread) -> ChatThread:
        thread.updated_at = datetime.now(timezone.utc)
        await self.session.commit()
        await self.session.refresh(thread)
        return thread

    async def soft_delete(self, thread: ChatThread) -> None:
        thread.deleted_at = datetime.now(timezone.utc)
        await self.session.commit()

    async def hard_delete(self, thread: ChatThread) -> None:
        await self.session.delete(thread)
        await self.session.commit()


class ChatMessageRepository:
    """Handles persistence and retrieval of chat messages within threads."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, message: ChatMessage) -> ChatMessage:
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(message)
        return message

    async def get_recent_history(
        self,
        thread_id: str,
        limit: int = 10,
    ) -> list[ChatMessage]:
        """
        Fetches the latest N messages for a thread in chronological (asc) order.
        Used to feed conversation history into LangChain memory/contextualization.
        """
        # Fetch latest messages descending
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.thread_id == thread_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        messages = list(result.scalars().all())
        # Return chronologically
        messages.reverse()
        return messages

    async def list_for_thread(
        self,
        thread_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[ChatMessage], int]:
        """Paginated retrieval of messages in a thread."""
        count_stmt = select(func.count(ChatMessage.id)).where(ChatMessage.thread_id == thread_id)
        total = await self.session.scalar(count_stmt) or 0

        stmt = (
            select(ChatMessage)
            .where(ChatMessage.thread_id == thread_id)
            .order_by(ChatMessage.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all(), total
