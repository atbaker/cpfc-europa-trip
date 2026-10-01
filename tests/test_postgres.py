"""Run against an already migrated local database with TEST_DATABASE_URL set."""

import asyncio
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, select, text
from temporalio.testing import ActivityEnvironment

from cpfc_trip.domain import CreateSession, Itinerary, Snapshot, Trip
from cpfc_trip.persistence.database import engine
from cpfc_trip.persistence.models import DeliveryRow, SessionRow
from cpfc_trip.persistence.repository import Repository
from cpfc_trip.temporal.activities import DeliveryActivities


@pytest.fixture
async def pg(settings):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL locking checks")
    config = settings.model_copy(update={"database_url": url})
    db = engine(config)
    repo = Repository(db, config)
    async with db.connect() as conn:
        assert await conn.scalar(text("select version_num from alembic_version"))
    yield repo
    await db.dispose()


async def cleanup(repo, sid):
    async with repo.sessions() as db, db.begin():
        await db.execute(delete(DeliveryRow).where(DeliveryRow.session_id == str(sid)))
        await db.execute(delete(SessionRow).where(SessionRow.id == str(sid)))


async def test_postgres_concurrent_submission_returns_one_session(pg, session_input):
    request = CreateSession(
        submission_id=uuid4(), email="postgres-check@example.com", brief=session_input.brief
    )
    results = await asyncio.gather(*(pg.create(request, "x" * 64) for _ in range(8)))
    sid = results[0].public_session_id
    try:
        assert all(x.public_session_id == sid for x in results)
        assert await pg.authorize(sid, "x" * 64)
        with pytest.raises(PermissionError):
            await pg.create(request, "y" * 64)
    finally:
        await cleanup(pg, sid)


async def test_postgres_concurrent_delivery_is_serialized(pg, session_input, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = await pg.create(
        CreateSession(
            submission_id=uuid4(), email="postgres-check@example.com", brief=session_input.brief
        ),
        "x" * 64,
    )
    now = datetime.now(UTC)
    snapshot = Snapshot(
        public_session_id=data.public_session_id,
        email_deadline=now,
        interaction_deadline=now,
        phase="finalizing",
        itinerary=Itinerary(
            revision=1,
            generated_at=now,
            trips=(Trip(fixture=data.fixtures[0], summary="Database integration check"),),
        ),
    )
    try:
        deliver = DeliveryActivities(pg).deliver_itinerary
        outputs = await asyncio.gather(
            *(ActivityEnvironment().run(deliver, snapshot) for _ in range(4))
        )
        assert len(set(outputs)) == 1
        async with pg.sessions() as db:
            row = await db.scalar(
                select(DeliveryRow).where(DeliveryRow.session_id == str(data.public_session_id))
            )
            assert row.attempts == 1 and row.status == "submitted"
    finally:
        await cleanup(pg, data.public_session_id)
