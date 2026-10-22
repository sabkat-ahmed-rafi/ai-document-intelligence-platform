"""create_document_chunks_and_pgvector

Revision ID: c3bb51f6204a
Revises: 9fb875d6dac9
Create Date: 2026-10-22 21:36:09.263973

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'c3bb51f6204a'
down_revision: Union[str, Sequence[str], None] = '9fb875d6dac9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable the pgvector extension in Supabase PostgreSQL
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Create the document_chunks table
    op.create_table(
        'document_chunks',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('document_id', sa.String(), nullable=False),
        sa.Column('collection_id', sa.String(), nullable=True),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('token_count', sa.Integer(), nullable=True),
        sa.Column('char_count', sa.Integer(), nullable=False),
        sa.Column('chunk_metadata', sa.JSON(), nullable=False),
        sa.Column('embedding', Vector(384), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # 3. Create relational B-tree indexes
    op.create_index(op.f('ix_document_chunks_document_id'), 'document_chunks', ['document_id'], unique=False)
    op.create_index(op.f('ix_document_chunks_collection_id'), 'document_chunks', ['collection_id'], unique=False)
    op.create_index(op.f('ix_document_chunks_user_id'), 'document_chunks', ['user_id'], unique=False)
    op.create_index('ix_document_chunks_user_doc', 'document_chunks', ['user_id', 'document_id'], unique=False)

    # 4. Create HNSW index for ultra-fast vector similarity search
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding 
        ON document_chunks USING hnsw (embedding vector_cosine_ops);
    """)

    # 5. Create RPC match function for vector search with filtering
    op.execute("""
        CREATE OR REPLACE FUNCTION match_document_chunks (
            query_embedding vector(384),
            match_count int DEFAULT 5,
            filter jsonb DEFAULT '{}'::jsonb
        )
        RETURNS TABLE (
            id text,
            document_id text,
            collection_id text,
            content text,
            metadata jsonb,
            similarity float
        )
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RETURN QUERY
            SELECT
                dc.id,
                dc.document_id,
                dc.collection_id,
                dc.content,
                dc.chunk_metadata::jsonb AS metadata,
                (1 - (dc.embedding <=> query_embedding))::float AS similarity
            FROM document_chunks dc
            WHERE 
                (filter->>'user_id' IS NULL OR dc.user_id = filter->>'user_id')
                AND (filter->>'collection_id' IS NULL OR dc.collection_id = filter->>'collection_id')
                AND (filter->>'document_id' IS NULL OR dc.document_id = filter->>'document_id')
            ORDER BY dc.embedding <=> query_embedding
            LIMIT match_count;
        END;
        $$;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS match_document_chunks(vector, int, jsonb);")
    op.execute("DROP INDEX IF EXISTS idx_document_chunks_embedding;")
    op.drop_index('ix_document_chunks_user_doc', table_name='document_chunks')
    op.drop_index(op.f('ix_document_chunks_user_id'), table_name='document_chunks')
    op.drop_index(op.f('ix_document_chunks_collection_id'), table_name='document_chunks')
    op.drop_index(op.f('ix_document_chunks_document_id'), table_name='document_chunks')
    op.drop_table('document_chunks')
