from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Document


class DocumentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, document: Document) -> Document:
        self.session.add(document)
        await self.session.commit()
        await self.session.refresh(document)
        return document

    async def get_by_id(
        self,
        document_id: str,
        user_id: str | None = None,
    ) -> Document | None:
        stmt = select(Document).where(
            Document.id == document_id,
            Document.deleted_at.is_(None),
        )
        if user_id:
            stmt = stmt.where(Document.user_id == user_id)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Document], int]:
        # Count total
        count_stmt = select(func.count(Document.id)).where(
            Document.user_id == user_id,
            Document.deleted_at.is_(None),
        )
        total = await self.session.scalar(count_stmt) or 0

        # Query records
        stmt = (
            select(Document)
            .where(
                Document.user_id == user_id,
                Document.deleted_at.is_(None),
            )
            .order_by(Document.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        documents = list(result.scalars().all())

        return documents, total

    async def update(self, document: Document) -> Document:
        await self.session.commit()
        await self.session.refresh(document)
        return document

    async def soft_delete(self, document: Document) -> None:
        document.deleted_at = datetime.now(timezone.utc)
        await self.session.commit()
