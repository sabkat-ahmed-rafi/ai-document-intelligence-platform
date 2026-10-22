from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import DocumentChunk


class DocumentChunkRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_many(self, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
        self.db.add_all(chunks)
        await self.db.commit()
        return chunks

    async def delete_by_document_id(self, document_id: str) -> int:
        stmt = delete(DocumentChunk).where(DocumentChunk.document_id == document_id)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount

    async def list_by_document_id(
        self,
        document_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[DocumentChunk], int]:
        count_stmt = (
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
        )
        total = await self.db.scalar(count_stmt) or 0

        stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all()), total

    async def search_similar(
        self,
        query_vector: list[float],
        user_id: str,
        collection_id: str | None = None,
        document_id: str | None = None,
        limit: int = 5,
    ) -> list[tuple[DocumentChunk, float]]:
        """
        Executes a cosine similarity vector search using pgvector's <=> distance operator.
        Returns tuples of (DocumentChunk, similarity_score).
        """
        distance_col = DocumentChunk.embedding.cosine_distance(query_vector)
        similarity_col = (1 - distance_col).label("similarity")

        filters = [DocumentChunk.user_id == user_id]
        if collection_id:
            filters.append(DocumentChunk.collection_id == collection_id)
        if document_id:
            filters.append(DocumentChunk.document_id == document_id)

        stmt = (
            select(DocumentChunk, similarity_col)
            .where(and_(*filters))
            .order_by(distance_col.asc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        rows = result.all()
        return [(row[0], float(row[1])) for row in rows]
