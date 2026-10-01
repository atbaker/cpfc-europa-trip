"""Encrypted contacts, saved itineraries and durable email deduplication."""

import sqlalchemy as sa
from alembic import op

revision = "20260906_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("submission_id", sa.String(36), unique=True, nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("access_hash", sa.String(64), nullable=False),
        sa.Column("email_hash", sa.String(64), nullable=False, index=True),
        sa.Column("encrypted_email", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("workflow_input", sa.JSON(), nullable=False),
        sa.Column("saved_itinerary", sa.JSON()),
    )
    op.create_table(
        "email_deliveries",
        sa.Column("session_id", sa.String(36), sa.ForeignKey("sessions.id"), primary_key=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_id", sa.String(100), unique=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )
    op.create_table(
        "email_webhooks",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("email_webhooks")
    op.drop_table("email_deliveries")
    op.drop_table("sessions")
