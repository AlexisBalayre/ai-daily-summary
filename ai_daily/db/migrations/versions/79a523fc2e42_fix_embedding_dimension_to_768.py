"""fix embedding dimension for qwen3-embedding:8b

Revision ID: 79a523fc2e42
Revises: 16e91a3601d2
Create Date: 2026-02-05 19:01:19.202753

"""
from typing import Sequence, Union

from alembic import op
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '79a523fc2e42'
down_revision: Union[str, Sequence[str], None] = '16e91a3601d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('articles', 'embedding',
               existing_type=Vector(1024),
               type_=Vector(4096),
               existing_nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column('articles', 'embedding',
               existing_type=Vector(4096),
               type_=Vector(1024),
               existing_nullable=True)
