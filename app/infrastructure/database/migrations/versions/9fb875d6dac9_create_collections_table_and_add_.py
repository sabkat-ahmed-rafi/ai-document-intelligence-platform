"""create collections table and add collection_id to documents

Revision ID: 9fb875d6dac9
Revises: e6512a1db762
Create Date: 2026-10-22 01:28:32.789840

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9fb875d6dac9'
down_revision: Union[str, Sequence[str], None] = 'e6512a1db762'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('collections',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('user_id', sa.String(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_collections_user_id'), 'collections', ['user_id'], unique=False)
    op.add_column('documents', sa.Column('collection_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_documents_collection_id'), 'documents', ['collection_id'], unique=False)
    op.create_foreign_key('fk_documents_collection_id', 'documents', 'collections', ['collection_id'], ['id'], ondelete='CASCADE')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_documents_collection_id', 'documents', type_='foreignkey')
    op.drop_index(op.f('ix_documents_collection_id'), table_name='documents')
    op.drop_column('documents', 'collection_id')
    op.drop_index(op.f('ix_collections_user_id'), table_name='collections')
    op.drop_table('collections')
