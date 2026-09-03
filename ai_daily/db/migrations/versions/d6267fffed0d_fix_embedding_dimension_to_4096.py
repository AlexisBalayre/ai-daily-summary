"""fix embedding dimension to 4096

Revision ID: d6267fffed0d
Revises: 79a523fc2e42
Create Date: 2026-02-05 19:03:01.505796

"""

from collections.abc import Sequence

from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "d6267fffed0d"
down_revision: str | Sequence[str] | None = "79a523fc2e42"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "articles",
        "embedding",
        existing_type=Vector(768),
        type_=Vector(4096),
        existing_nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        "articles",
        "embedding",
        existing_type=Vector(4096),
        type_=Vector(768),
        existing_nullable=True,
    )
