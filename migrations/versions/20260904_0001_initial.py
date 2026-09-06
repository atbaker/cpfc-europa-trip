"""Create contact, session-access, and email-delivery tables."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260904_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "contacts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "sessions",
        sa.Column("public_id", sa.String(length=36), primary_key=True),
        sa.Column("workflow_id", sa.String(length=128), nullable=False, unique=True),
        sa.Column("request_id", sa.String(length=36), nullable=False, unique=True),
        sa.Column(
            "contact_id",
            sa.String(length=36),
            sa.ForeignKey("contacts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("access_token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "email_deliveries",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("idempotency_key", sa.String(length=180), nullable=False, unique=True),
        sa.Column("public_id", sa.String(length=36), nullable=False, index=True),
        sa.Column(
            "contact_id",
            sa.String(length=36),
            sa.ForeignKey("contacts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("itinerary_revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("preview_html", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("email_deliveries")
    op.drop_table("sessions")
    op.drop_table("contacts")
