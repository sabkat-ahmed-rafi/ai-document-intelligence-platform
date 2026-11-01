"""create_chat_threads_and_messages

Revision ID: b7e3c1a9d5f2
Revises: f4a8b1c2d3e4
Create Date: 2026-11-01 23:12:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7e3c1a9d5f2'
down_revision: Union[str, Sequence[str], None] = 'f4a8b1c2d3e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create chat_threads table
    op.create_table(
        'chat_threads',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('collection_id', sa.String(), nullable=True),
        sa.Column('document_id', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index(op.f('ix_chat_threads_user_id'), 'chat_threads', ['user_id'], unique=False)
    op.create_index(op.f('ix_chat_threads_collection_id'), 'chat_threads', ['collection_id'], unique=False)
    op.create_index(op.f('ix_chat_threads_document_id'), 'chat_threads', ['document_id'], unique=False)

    # 2. Create chat_messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('thread_id', sa.String(36), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),  # 'user', 'assistant', 'system'
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('citations', sa.JSON(), nullable=True),  # Array of CitationSource objects
        sa.Column('model', sa.String(100), nullable=True),
        sa.Column('provider', sa.String(50), nullable=True),
        sa.Column('execution_time_ms', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['thread_id'], ['chat_threads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index(op.f('ix_chat_messages_thread_id'), 'chat_messages', ['thread_id'], unique=False)
    op.create_index('ix_chat_messages_thread_created', 'chat_messages', ['thread_id', 'created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_chat_messages_thread_created', table_name='chat_messages')
    op.drop_index(op.f('ix_chat_messages_thread_id'), table_name='chat_messages')
    op.drop_table('chat_messages')

    op.drop_index(op.f('ix_chat_threads_document_id'), table_name='chat_threads')
    op.drop_index(op.f('ix_chat_threads_collection_id'), table_name='chat_threads')
    op.drop_index(op.f('ix_chat_threads_user_id'), table_name='chat_threads')
    op.drop_table('chat_threads')
