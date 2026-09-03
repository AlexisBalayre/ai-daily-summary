"""add enrichment fields to articles

Revision ID: e0bcaa41593c
Revises: bcbf1844ce46
Create Date: 2026-02-07 21:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e0bcaa41593c"
down_revision: str | Sequence[str] | None = "bcbf1844ce46"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add enrichment fields to articles table."""
    # Add summary field for AI-generated summaries
    op.add_column("articles", sa.Column("summary", sa.Text(), nullable=True))

    # Add category field for article classification
    op.add_column("articles", sa.Column("category", sa.String(length=50), nullable=True))

    # Add is_ai_related field for AI relevance classification
    op.add_column("articles", sa.Column("is_ai_related", sa.Boolean(), nullable=True))

    # Add enriched_at timestamp to track when enrichment was performed
    op.add_column("articles", sa.Column("enriched_at", sa.DateTime(), nullable=True))

    # Add is_duplicate field with default False
    op.add_column(
        "articles", sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default="false")
    )

    # Add duplicate_of_id self-referential foreign key
    op.add_column("articles", sa.Column("duplicate_of_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_articles_duplicate_of_id", "articles", "articles", ["duplicate_of_id"], ["id"]
    )

    # Add index on enriched_at for querying unenriched articles
    op.create_index("idx_articles_enriched_at", "articles", ["enriched_at"], unique=False)

    # Add index on is_duplicate for filtering
    op.create_index("idx_articles_is_duplicate", "articles", ["is_duplicate"], unique=False)

    # Add index on category for filtering
    op.create_index("idx_articles_category", "articles", ["category"], unique=False)


def downgrade() -> None:
    """Remove enrichment fields from articles table."""
    op.drop_index("idx_articles_category", table_name="articles")
    op.drop_index("idx_articles_is_duplicate", table_name="articles")
    op.drop_index("idx_articles_enriched_at", table_name="articles")
    op.drop_constraint("fk_articles_duplicate_of_id", "articles", type_="foreignkey")
    op.drop_column("articles", "duplicate_of_id")
    op.drop_column("articles", "is_duplicate")
    op.drop_column("articles", "enriched_at")
    op.drop_column("articles", "is_ai_related")
    op.drop_column("articles", "category")
    op.drop_column("articles", "summary")
