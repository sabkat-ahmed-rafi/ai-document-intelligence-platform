from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database import Base, TimestampMixin
from .enums import FileStatus


class File(TimestampMixin, Base):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(
        primary_key=True
    )

    original_name: Mapped[str] = mapped_column(
        nullable=False
    )

    storage_key: Mapped[str] = mapped_column(
        nullable=False
    )

    provider: Mapped[str] = mapped_column(
        nullable=False
    )

    mime_type: Mapped[str] = mapped_column(
        nullable=False
    )

    size: Mapped[int] = mapped_column(
        nullable=False
    )

    owner_type: Mapped[str] = mapped_column(
        nullable=False,
        index=True,
    )

    owner_id: Mapped[str] = mapped_column(
        nullable=False,
        index=True,
    )

    category: Mapped[str] = mapped_column(
        nullable=False,
        index=True,
    )

    is_public: Mapped[bool] = mapped_column(
        default=False,
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        default=FileStatus.ACTIVE.value,
        nullable=False,
        index=True,
    )