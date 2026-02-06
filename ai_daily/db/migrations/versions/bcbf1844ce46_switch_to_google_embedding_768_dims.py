"""switch to google embedding 768 dims

Revision ID: bcbf1844ce46
Revises: d6267fffed0d
Create Date: 2026-02-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = 'bcbf1844ce46'
down_revision: Union[str, Sequence[str], None] = 'd6267fffed0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - switch to Google text-embedding-004 (768 dims)."""
    # Clear existing embeddings since they're incompatible with new dimension
    op.execute("UPDATE articles SET embedding = NULL")
    op.alter_column('articles', 'embedding',
               existing_type=Vector(4096),
               type_=Vector(768),
               existing_nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("UPDATE articles SET embedding = NULL")
    op.alter_column('articles', 'embedding',
               existing_type=Vector(768),
               type_=Vector(4096),
               existing_nullable=True)
