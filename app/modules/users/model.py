from sqlalchemy.orm import Mapped, mapped_column

from infrastructure.database import Base, TimestampMixin, SoftDeleteMixin


class Users(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        primary_key=True
    )

    email: Mapped[str] = mapped_column(
        unique=True,
        index=True,
        nullable=False
    )

    password_hash: Mapped[str] = mapped_column(
        nullable=True,
    )

    first_name: Mapped[str | None] = mapped_column(
        nullable=True,
    )

    last_name: Mapped[str | None] = mapped_column(
        nullable=True,
    )

    role: Mapped[str] = mapped_column(
        default="user",
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )

    is_verified: Mapped[bool] = mapped_column(
        default=True,
        nullable=False,
    )


# Convenient alias for singular naming
User = Users