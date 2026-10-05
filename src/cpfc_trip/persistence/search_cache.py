"""24-hour shared cache of normalized provider results, split by search domain."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from pydantic import ValidationError
from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from cpfc_trip.domain import SearchBatch, SearchSpec
from cpfc_trip.persistence.models import SearchCacheRow

SearchMode = Literal["flight", "rail", "stay"]
CACHE_TTL = timedelta(hours=24)


def cache_identity(spec: SearchSpec, mode: SearchMode) -> tuple[str, str]:
    """Return separate hotel or transport namespace and a request-safe key.

    The route key includes the exact party because flight and rail prices depend on it.
    Hotel results can be shared across route candidates for the same city and stay.
    """
    common = (str(spec.outbound_date), str(spec.return_date), spec.party.model_dump(mode="json"))
    fields: tuple[object, ...]
    if mode == "stay":
        namespace = "hotel"
        fields = (
            "hotel-v1",
            spec.fixture.city.casefold(),
            *common,
            spec.budget_tier,
            spec.private_room,
            spec.private_bathroom,
        )
    else:
        namespace = "transport"
        fields = (
            "transport-v1",
            spec.fixture.id,
            spec.route.model_dump(mode="json"),
            mode,
            *common,
        )
    payload = json.dumps(fields, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return namespace, hashlib.sha256(payload.encode()).hexdigest()


class SearchCache:
    """Share positive normalized batches across workers without changing their evidence times."""

    def __init__(self, database: AsyncEngine) -> None:
        self.sessions = async_sessionmaker(database, expire_on_commit=False)

    async def get(
        self, spec: SearchSpec, mode: SearchMode, *, now: datetime | None = None
    ) -> SearchBatch | None:
        """Return an unexpired batch with zero new provider calls, or ``None``."""
        namespace, key = cache_identity(spec, mode)
        checked = now or datetime.now(UTC)
        async with self.sessions() as session:
            row = await session.get(SearchCacheRow, (namespace, key))
        if row is None:
            return None
        expires_at = row.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at <= checked:
            return None
        try:
            return SearchBatch.model_validate(row.payload).model_copy(update={"calls": 0})
        except ValidationError:
            return None

    async def put(
        self,
        spec: SearchSpec,
        mode: SearchMode,
        batch: SearchBatch,
        *,
        now: datetime | None = None,
    ) -> None:
        """Keep only successful batches; opportunistically remove expired rows."""
        if not (batch.stays if mode == "stay" else batch.journeys):
            return
        namespace, key = cache_identity(spec, mode)
        checked = now or datetime.now(UTC)
        payload = cast(
            dict[str, object],
            json.loads(batch.model_copy(update={"calls": 0}).model_dump_json()),
        )
        values = {"payload": payload, "expires_at": checked + CACHE_TTL}
        async with self.sessions.begin() as session:
            await session.execute(
                delete(SearchCacheRow).where(SearchCacheRow.expires_at <= checked)
            )
            try:
                async with session.begin_nested():
                    session.add(SearchCacheRow(namespace=namespace, key=key, **values))
                    await session.flush()
            except IntegrityError:
                await session.execute(
                    update(SearchCacheRow)
                    .where(SearchCacheRow.namespace == namespace, SearchCacheRow.key == key)
                    .values(**values)
                )
