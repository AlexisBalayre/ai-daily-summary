"""store timestamps as timestamptz

Revision ID: a1c7d2e9f3b4
Revises: e0bcaa41593c
Create Date: 2026-09-03 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "a1c7d2e9f3b4"
down_revision: str | Sequence[str] | None = "e0bcaa41593c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Every DateTime column in the schema, grouped so each table is rewritten once.
# Existing values were written by datetime.utcnow(), so they are reinterpreted
# as UTC rather than as session-local time.
TIMESTAMP_COLUMNS: dict[str, list[str]] = {
    "sources": ["created_at"],
    "articles": ["published_at", "ingested_at", "enriched_at"],
    "daily_summaries": ["date", "created_at"],
    "leaderboard_snapshots": ["captured_at"],
    "job_runs": ["started_at", "finished_at"],
}


def _ensure_leaderboard_table() -> None:
    """Create leaderboard_snapshots when the schema predates its migration.

    The table was only ever created through Base.metadata.create_all(), so
    databases managed purely by Alembic do not have it yet.
    """
    inspector = sa.inspect(op.get_bind())
    if "leaderboard_snapshots" in inspector.get_table_names():
        return
    op.create_table(
        "leaderboard_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("board", sa.String(length=100), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=True),
        sa.Column("rows", postgresql.JSONB(), nullable=True),
        sa.Column("row_count", sa.Integer(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "idx_leaderboard_board_captured", "leaderboard_snapshots", ["board", "captured_at"]
    )


def _alter_types(target: str) -> None:
    for table, columns in TIMESTAMP_COLUMNS.items():
        clauses = ", ".join(
            f"ALTER COLUMN {column} TYPE {target} USING {column} AT TIME ZONE 'UTC'"
            for column in columns
        )
        op.execute(f"ALTER TABLE {table} {clauses}")


def upgrade() -> None:
    """Convert naive UTC timestamps to timestamptz (one table rewrite each)."""
    _ensure_leaderboard_table()
    _alter_types("TIMESTAMP WITH TIME ZONE")


def downgrade() -> None:
    """Revert to naive timestamps holding UTC wall-clock values."""
    _alter_types("TIMESTAMP WITHOUT TIME ZONE")
