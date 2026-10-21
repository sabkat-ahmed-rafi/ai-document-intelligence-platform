from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Collection


class CollectionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, collection: Collection) -> Collection:
        self.session.add(collection)
        await self.session.commit()
        await self.session.refresh(collection)
        return collection

    async def get_by_id(
        self,
        collection_id: str,
        user_id: str,
    ) -> Collection | None:
        stmt = select(Collection).where(
            Collection.id == collection_id,
            Collection.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_name(
        self,
        name: str,
        user_id: str,
    ) -> Collection | None:
        stmt = select(Collection).where(
            func.lower(Collection.name) == name.strip().lower(),
            Collection.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_document_count(self, collection_id: str) -> int:
        from modules.documents.models import Document

        stmt = select(func.count(Document.id)).where(
            Document.collection_id == collection_id,
            Document.deleted_at.is_(None),
        )
        return await self.session.scalar(stmt) or 0

    async def list_for_user(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[tuple[Collection, int]], int]:
        from modules.documents.models import Document

        # Count total collections
        total_stmt = select(func.count(Collection.id)).where(Collection.user_id == user_id)
        total = await self.session.scalar(total_stmt) or 0

        # Query collections with active document counts
        stmt = (
            select(
                Collection,
                func.count(Document.id).filter(Document.deleted_at.is_(None)).label("doc_count"),
            )
            .outerjoin(Document, Document.collection_id == Collection.id)
            .where(Collection.user_id == user_id)
            .group_by(Collection.id)
            .order_by(Collection.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        rows = list(result.all())
        return rows, total

    async def update(self, collection: Collection) -> Collection:
        await self.session.commit()
        await self.session.refresh(collection)
        return collection

    async def delete(self, collection: Collection) -> None:
        """Hard delete collection, triggering ON DELETE CASCADE on linked documents."""
        await self.session.delete(collection)
        await self.session.commit()
