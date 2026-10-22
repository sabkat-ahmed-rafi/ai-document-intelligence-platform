from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.database import Base, TimestampMixin, SoftDeleteMixin
from .enums import DocumentStatus


class Document(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(primary_key=True)

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    collection_id: Mapped[str | None] = mapped_column(
        ForeignKey("collections.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )

    file_id: Mapped[str] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    mime_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    file_size: Mapped[int] = mapped_column(
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default=DocumentStatus.PENDING.value,
        index=True,
        nullable=False,
    )

    error_message: Mapped[str | None] = mapped_column(
        nullable=True,
    )

    doc_metadata: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
    )

    # Relationships
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
