"""Short shared search cache contracts, independent of provider traffic."""

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from cpfc_trip.config import Settings
from cpfc_trip.domain import Party, SearchBatch, SearchSpec, SessionInput
from cpfc_trip.persistence.database import engine
from cpfc_trip.persistence.models import Base
from cpfc_trip.persistence.search_cache import SearchCache
from cpfc_trip.planner.recorded import sample
from cpfc_trip.temporal.activities import SearchActivities

CHECKED = datetime(2026, 10, 5, 12, tzinfo=UTC)


@pytest.fixture
async def cache_engine(settings: Settings, tmp_path: Path) -> AsyncIterator[AsyncEngine]:
    """Create a separate database so two cache instances share durable rows."""
    database = engine(
        settings.model_copy(update={"database_url": f"sqlite+aiosqlite:///{tmp_path / 'cache.db'}"})
    )
    async with database.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield database
    await database.dispose()


def search_spec(data: SessionInput) -> SearchSpec:
    """Build a dated request with a known origin, destination and party."""
    return SearchSpec(
        fixture=data.fixtures[0],
        route=data.routes[0],
        party=Party(adults=2),
        outbound_date=date(2026, 10, 14),
        return_date=date(2026, 10, 16),
    )


async def test_transport_cache_is_shared_for_24_hours_and_party_safe(
    cache_engine: AsyncEngine, session_input: SessionInput
) -> None:
    """Only the same route, dates, mode and travellers may reuse a journey."""
    request = search_spec(session_input)
    batch = sample(request, "flight").model_copy(update={"calls": 3})
    writer = SearchCache(cache_engine)
    reader = SearchCache(cache_engine)
    await writer.put(request, "flight", batch, now=CHECKED)

    hit = await reader.get(request, "flight", now=CHECKED + timedelta(hours=23))
    assert hit is not None and hit.calls == 0
    assert hit.journeys == batch.journeys
    assert await reader.get(request, "rail", now=CHECKED) is None
    assert (
        await reader.get(
            request.model_copy(update={"party": Party(adults=1)}), "flight", now=CHECKED
        )
        is None
    )
    assert (
        await reader.get(
            request.model_copy(update={"return_date": date(2026, 10, 17)}), "flight", now=CHECKED
        )
        is None
    )
    assert await reader.get(request, "flight", now=CHECKED + timedelta(hours=24)) is None


async def test_hotel_cache_ignores_route_but_keys_preferences(
    cache_engine: AsyncEngine, session_input: SessionInput
) -> None:
    """Accommodation can be reused across routes, never across party or room needs."""
    request = search_spec(session_input)
    batch = sample(request, "stay").model_copy(update={"calls": 3})
    cache = SearchCache(cache_engine)
    await cache.put(request, "stay", batch, now=CHECKED)

    other_route = request.model_copy(update={"route": session_input.routes[1]})
    hit = await cache.get(other_route, "stay", now=CHECKED)
    assert hit is not None and hit.calls == 0 and hit.stays == batch.stays
    assert (
        await cache.get(request.model_copy(update={"budget_tier": "comfort"}), "stay", now=CHECKED)
        is None
    )
    assert (
        await cache.get(request.model_copy(update={"private_bathroom": True}), "stay", now=CHECKED)
        is None
    )
    assert (
        await cache.get(request.model_copy(update={"party": Party(adults=1)}), "stay", now=CHECKED)
        is None
    )
    assert await cache.get(request, "stay", now=CHECKED + timedelta(hours=24)) is None


async def test_incomplete_results_are_not_shared(
    cache_engine: AsyncEngine, session_input: SessionInput
) -> None:
    """Provider failures and no-result searches must be retried on the next request."""
    cache = SearchCache(cache_engine)
    request = search_spec(session_input)
    await cache.put(request, "flight", SearchBatch(gaps=("Provider failed",), calls=1), now=CHECKED)
    assert await cache.get(request, "flight", now=CHECKED) is None


async def test_activity_uses_shared_cache_without_charging_calls(
    cache_engine: AsyncEngine, session_input: SessionInput, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second worker uses the first worker's result and original quote times."""
    request = search_spec(session_input)
    batch = sample(request, "flight").model_copy(update={"calls": 2})
    calls = 0

    async def fake_acquire(spec: SearchSpec, mode: str) -> SearchBatch:
        nonlocal calls
        assert spec == request and mode == "flight"
        calls += 1
        return batch

    monkeypatch.setattr("cpfc_trip.temporal.activities.acquire", fake_acquire)
    first = SearchActivities(SearchCache(cache_engine))
    second = SearchActivities(SearchCache(cache_engine))
    assert await first.search_flights(request) == batch
    reused = await second.search_flights(request)
    assert reused.calls == 0
    assert reused.journeys == batch.journeys
    assert calls == 1


async def test_cache_failure_falls_through_to_provider(
    cache_engine: AsyncEngine, session_input: SessionInput, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cache outage must not prevent a paid live search from proceeding."""
    request = search_spec(session_input)
    batch = sample(request, "flight")
    provider_calls = 0

    async def broken_get(*args: object, **kwargs: object) -> None:
        raise SQLAlchemyError("cache unavailable")

    async def fake_acquire(spec: SearchSpec, mode: str) -> SearchBatch:
        nonlocal provider_calls
        provider_calls += 1
        return batch

    monkeypatch.setattr(SearchCache, "get", broken_get)
    monkeypatch.setattr("cpfc_trip.temporal.activities.acquire", fake_acquire)
    assert await SearchActivities(SearchCache(cache_engine)).search_flights(request) == batch
    assert provider_calls == 1
