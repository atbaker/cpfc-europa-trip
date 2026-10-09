"""Public preview data is kept for at most 30 days in our database."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from cpfc_trip.persistence.models import DeliveryRow, SessionRow, WebhookRow
from cpfc_trip.persistence.retention import prune_expired


async def test_prune_expired_removes_old_sessions_and_deliveries(repository) -> None:
    now = datetime(2026, 10, 9, tzinfo=UTC)
    old = now - timedelta(days=31)
    recent = now - timedelta(days=29)
    async with repository.sessions() as db:
        for sid, created_at in (("old", old), ("recent", recent)):
            db.add(
                SessionRow(
                    id=sid,
                    submission_id=sid,
                    request_hash="r",
                    access_hash="a",
                    email_hash="e",
                    encrypted_email=b"encrypted",
                    created_at=created_at,
                    workflow_input={},
                )
            )
            db.add(
                DeliveryRow(
                    session_id=sid,
                    payload_hash="p",
                    payload={},
                    created_at=created_at,
                )
            )
        db.add(WebhookRow(id="old", received_at=old, event_type="sent"))
        db.add(WebhookRow(id="recent", received_at=recent, event_type="sent"))
        await db.commit()

    assert await prune_expired(repository.sessions, now=now) == (1, 1, 1)
    async with repository.sessions() as db:
        assert list(await db.scalars(select(SessionRow.id))) == ["recent"]
        assert list(await db.scalars(select(DeliveryRow.session_id))) == ["recent"]
        assert list(await db.scalars(select(WebhookRow.id))) == ["recent"]
