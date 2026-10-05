"""Add 24-hour shared transport and hotel result cache."""

import sqlalchemy as sa
from alembic import op

revision = "20261005_0002"
down_revision = "20260906_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_cache",
        sa.Column("namespace", sa.String(16), primary_key=True),
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_search_cache_expires_at", "search_cache", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_search_cache_expires_at", table_name="search_cache")
    op.drop_table("search_cache")
