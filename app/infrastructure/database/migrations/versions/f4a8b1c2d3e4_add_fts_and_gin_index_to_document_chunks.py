"""add_fts_and_gin_index_to_document_chunks

Revision ID: f4a8b1c2d3e4
Revises: c3bb51f6204a
Create Date: 2026-11-01 22:26:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4a8b1c2d3e4'
down_revision: Union[str, Sequence[str], None] = 'c3bb51f6204a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add fts_vector GENERATED column stored for English full-text search
    op.execute("""
        ALTER TABLE document_chunks 
        ADD COLUMN IF NOT EXISTS fts_vector tsvector 
        GENERATED ALWAYS AS (to_tsvector('english', coalesce(content, ''))) STORED;
    """)

    # 2. Create GIN index for sub-millisecond keyword lookup
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_chunks_fts 
        ON document_chunks USING gin (fts_vector);
    """)

    # 3. Create Supabase RPC Hybrid Search function with Reciprocal Rank Fusion (RRF)
    op.execute("""
        CREATE OR REPLACE FUNCTION match_document_chunks_hybrid (
            query_embedding vector(384),
            query_text text,
            match_count int DEFAULT 5,
            rrf_k int DEFAULT 60,
            filter jsonb DEFAULT '{}'::jsonb
        )
        RETURNS TABLE (
            id text,
            document_id text,
            collection_id text,
            content text,
            metadata jsonb,
            vector_similarity float,
            keyword_rank float,
            rrf_score float
        )
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RETURN QUERY
            WITH vector_matches AS (
                SELECT
                    dc.id,
                    dc.document_id,
                    dc.collection_id,
                    dc.content,
                    dc.chunk_metadata::jsonb AS metadata,
                    (1 - (dc.embedding <=> query_embedding))::float AS sim,
                    ROW_NUMBER() OVER (ORDER BY dc.embedding <=> query_embedding) AS v_rank
                FROM document_chunks dc
                WHERE
                    (filter->>'user_id' IS NULL OR dc.user_id = filter->>'user_id')
                    AND (filter->>'collection_id' IS NULL OR dc.collection_id = filter->>'collection_id')
                    AND (filter->>'document_id' IS NULL OR dc.document_id = filter->>'document_id')
                LIMIT match_count * 2
            ),
            keyword_matches AS (
                SELECT
                    dc.id,
                    dc.document_id,
                    dc.collection_id,
                    dc.content,
                    dc.chunk_metadata::jsonb AS metadata,
                    ts_rank_cd(dc.fts_vector, websearch_to_tsquery('english', query_text))::float AS k_score,
                    ROW_NUMBER() OVER (ORDER BY ts_rank_cd(dc.fts_vector, websearch_to_tsquery('english', query_text)) DESC) AS k_rank
                FROM document_chunks dc
                WHERE
                    dc.fts_vector @@ websearch_to_tsquery('english', query_text)
                    AND (filter->>'user_id' IS NULL OR dc.user_id = filter->>'user_id')
                    AND (filter->>'collection_id' IS NULL OR dc.collection_id = filter->>'collection_id')
                    AND (filter->>'document_id' IS NULL OR dc.document_id = filter->>'document_id')
                LIMIT match_count * 2
            ),
            fused AS (
                SELECT
                    COALESCE(v.id, k.id) AS chunk_id,
                    COALESCE(v.document_id, k.document_id) AS doc_id,
                    COALESCE(v.collection_id, k.collection_id) AS col_id,
                    COALESCE(v.content, k.content) AS chunk_content,
                    COALESCE(v.metadata, k.metadata) AS chunk_meta,
                    COALESCE(v.sim, 0.0) AS sim_val,
                    COALESCE(k.k_score, 0.0) AS rank_val,
                    (COALESCE(1.0 / (rrf_k + v.v_rank), 0.0) + COALESCE(1.0 / (rrf_k + k.k_rank), 0.0))::float AS fusion_score
                FROM vector_matches v
                FULL OUTER JOIN keyword_matches k ON v.id = k.id
            )
            SELECT
                f.chunk_id AS id,
                f.doc_id AS document_id,
                f.col_id AS collection_id,
                f.chunk_content AS content,
                f.chunk_meta AS metadata,
                f.sim_val AS vector_similarity,
                f.rank_val AS keyword_rank,
                f.fusion_score AS rrf_score
            FROM fused f
            ORDER BY f.fusion_score DESC
            LIMIT match_count;
        END;
        $$;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS match_document_chunks_hybrid(vector, text, int, int, jsonb);")
    op.execute("DROP INDEX IF EXISTS idx_document_chunks_fts;")
    op.execute("ALTER TABLE document_chunks DROP COLUMN IF EXISTS fts_vector;")
