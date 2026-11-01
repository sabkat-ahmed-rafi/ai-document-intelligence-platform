from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.database import Base, SoftDeleteMixin, TimestampMixin


class ChatThread(TimestampMixin, SoftDeleteMixin, Base):
    """Represents a persistent conversation thread scoped to a user and optional knowledge base."""

    __tablename__ = "chat_threads"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="New Conversation",
    )

    collection_id: Mapped[str | None] = mapped_column(
        ForeignKey("collections.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    document_id: Mapped[str | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    # Relationships
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="thread",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at.asc()",
        lazy="selectin",
    )


class ChatMessage(Base):
    """Represents an individual message (user question or assistant answer) within a thread."""

    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)

    thread_id: Mapped[str] = mapped_column(
        ForeignKey("chat_threads.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,  # "user", "assistant", "system"
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    citations: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    provider: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    execution_time_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    thread: Mapped[ChatThread] = relationship(
        "ChatThread",
        back_populates="messages",
    )
