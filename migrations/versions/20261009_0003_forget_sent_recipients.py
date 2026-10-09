"""Erase locally stored recipients for emails already accepted by the provider."""

import sqlalchemy as sa
from alembic import op

revision = "20261009_0003"
down_revision = "20261005_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Remove local recipient values from existing accepted deliveries."""
    sessions = sa.table(
        "sessions",
        sa.column("id", sa.String(36)),
        sa.column("encrypted_email", sa.LargeBinary()),
        sa.column("email_hash", sa.String(64)),
    )
    deliveries = sa.table(
        "email_deliveries",
        sa.column("session_id", sa.String(36)),
        sa.column("provider_id", sa.String(100)),
    )
    sent = sa.exists(
        sa.select(deliveries.c.session_id).where(
            deliveries.c.session_id == sessions.c.id,
            deliveries.c.provider_id.is_not(None),
        )
    )
    op.get_bind().execute(
        sa.update(sessions).where(sent).values(encrypted_email=b"", email_hash="")
    )


def downgrade() -> None:
    """Recipient erasure cannot be reversed."""
