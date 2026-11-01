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

    async def search_keywords(
        self,
        query_text: str,
        user_id: str,
        collection_id: str | None = None,
        document_id: str | None = None,
        limit: int = 5,
    ) -> list[tuple[DocumentChunk, float]]:
        """
        Executes a PostgreSQL Full-Text Search (BM25) using websearch_to_tsquery and ts_rank_cd.
        Returns tuples of (DocumentChunk, bm25_rank_score).
        """
        clean_query = query_text.strip()
        if not clean_query:
            return []

        ts_query = func.websearch_to_tsquery("english", clean_query)
        fts_expr = func.to_tsvector("english", DocumentChunk.content)
        rank_col = func.ts_rank_cd(fts_expr, ts_query).label("rank")

        filters = [
            DocumentChunk.user_id == user_id,
            fts_expr.op("@@")(ts_query),
        ]
        if collection_id:
            filters.append(DocumentChunk.collection_id == collection_id)
        if document_id:
            filters.append(DocumentChunk.document_id == document_id)

        stmt = (
            select(DocumentChunk, rank_col)
            .where(and_(*filters))
            .order_by(rank_col.desc())
            .limit(limit)
        )

        result = await self.db.execute(stmt)
        rows = result.all()
        return [(row[0], float(row[1])) for row in rows]

    async def search_hybrid(
        self,
        query_vector: list[float],
        query_text: str,
        user_id: str,
        collection_id: str | None = None,
        document_id: str | None = None,
        limit: int = 5,
        rrf_k: int = 60,
    ):
        """
        Executes parallel vector and full-text keyword searches, then blends the results
        using Reciprocal Rank Fusion (RRF).
        """
        import asyncio
        from .search.rrf import compute_reciprocal_rank_fusion

        # Fetch candidate pools in parallel
        candidate_limit = max(limit * 2, 10)
        vector_task = self.search_similar(
            query_vector=query_vector,
            user_id=user_id,
            collection_id=collection_id,
            document_id=document_id,
            limit=candidate_limit,
        )
        keyword_task = self.search_keywords(
            query_text=query_text,
            user_id=user_id,
            collection_id=collection_id,
            document_id=document_id,
            limit=candidate_limit,
        )

        vector_results, keyword_results = await asyncio.gather(vector_task, keyword_task)

        return compute_reciprocal_rank_fusion(
            vector_results=vector_results,
            keyword_results=keyword_results,
            rrf_k=rrf_k,
            limit=limit,
        )
