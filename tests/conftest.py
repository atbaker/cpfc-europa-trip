from datetime import UTC, datetime
from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from cpfc_trip.catalog import load_catalog, validate_brief
from cpfc_trip.config import Settings
from cpfc_trip.domain import Brief, SessionInput
from cpfc_trip.persistence.database import engine
from cpfc_trip.persistence.models import Base
from cpfc_trip.persistence.repository import Repository


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        app_env="test",
        planner_mode="recorded",
        email_mode="preview",
        contact_encryption_key=Fernet.generate_key().decode(),
        session_secret="test-secret",
        database_url="sqlite+aiosqlite:///:memory:",
    )


@pytest.fixture
def session_input():
    fixtures, routes = load_catalog()
    brief = validate_brief(
        Brief(fixture_ids=(fixtures[0].id,)), fixtures, datetime(2026, 9, 6, tzinfo=UTC)
    )
    sid = uuid4()
    return SessionInput(
        public_session_id=sid,
        contact_id=sid,
        brief=brief,
        fixtures=(fixtures[0],),
        routes=tuple(r for r in routes if r.fixture_id == fixtures[0].id),
        planner_mode="recorded",
    )


@pytest.fixture
async def repository(settings):
    db = engine(settings)
    async with db.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield Repository(db, settings)
    await db.dispose()
