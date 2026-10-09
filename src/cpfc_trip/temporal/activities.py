import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from temporalio import activity
from temporalio.exceptions import ApplicationError

from cpfc_trip.domain import SearchBatch, SearchSpec, Snapshot
from cpfc_trip.emailing import render
from cpfc_trip.persistence.models import DeliveryRow, SessionRow
from cpfc_trip.persistence.repository import Repository, digest
from cpfc_trip.persistence.search_cache import SearchCache, SearchMode
from cpfc_trip.planner.providers.searchapi import acquire
from cpfc_trip.resend import send


class SearchActivities:
    """Search with a shared, best-effort cache before contacting paid providers."""

    def __init__(self, cache: SearchCache) -> None:
        self.cache = cache

    async def _search(self, spec: SearchSpec, mode: SearchMode) -> SearchBatch:
        try:
            async with asyncio.timeout(1):
                cached = await self.cache.get(spec, mode)
            if cached is not None:
                return cached
        except (SQLAlchemyError, TimeoutError):
            logging.warning("Shared search cache read failed", exc_info=True)
        result = await acquire(spec, mode)
        try:
            async with asyncio.timeout(1):
                await self.cache.put(spec, mode, result)
        except (SQLAlchemyError, TimeoutError):
            logging.warning("Shared search cache write failed", exc_info=True)
        return result

    @activity.defn(name="search_flights")
    async def search_flights(self, spec: SearchSpec) -> SearchBatch:
        return await self._search(spec, "flight")

    @activity.defn(name="search_trains")
    async def search_trains(self, spec: SearchSpec) -> SearchBatch:
        return await self._search(spec, "rail")

    @activity.defn(name="search_stays")
    async def search_stays(self, spec: SearchSpec) -> SearchBatch:
        return await self._search(spec, "stay")


def _erase_local_recipient(session: SessionRow) -> None:
    session.encrypted_email = b""
    session.email_hash = ""


class DeliveryActivities:
    def __init__(self, repository: Repository):
        self.repository = repository

    @activity.defn
    async def deliver_itinerary(self, snapshot: Snapshot) -> str:
        repo = self.repository
        settings = repo.settings
        payload = render(snapshot)
        payload_hash = digest(json.dumps(payload, sort_keys=True))
        sid = str(snapshot.public_session_id)
        # Serialize all attempts for this session, including a worker recovering after send.
        async with repo.sessions() as db, db.begin():
            row = await db.scalar(select(SessionRow).where(SessionRow.id == sid).with_for_update())
            if row is None or row.deleted_at:
                raise ApplicationError("Session is deleted", non_retryable=True)
            delivery = await db.get(DeliveryRow, sid)
            if delivery is None:
                delivery = DeliveryRow(
                    session_id=sid,
                    payload={
                        **payload,
                        "from": settings.resend_from_email,
                        "tags": [{"name": "session_id", "value": sid}],
                    },
                    payload_hash=payload_hash,
                    created_at=datetime.now(UTC),
                    attempts=0,
                )
                db.add(delivery)
            elif delivery.payload_hash != payload_hash:
                raise ApplicationError("Frozen email payload mismatch", non_retryable=True)
            elif delivery.provider_id:
                _erase_local_recipient(row)
                return str(delivery.provider_id)
            row.saved_itinerary = (
                json.loads(snapshot.itinerary.model_dump_json()) if snapshot.itinerary else None
            )
        # Persist first-attempt time BEFORE any external send; it survives ambiguous outcomes.
        async with repo.sessions() as db, db.begin():
            delivery = await db.scalar(
                select(DeliveryRow).where(DeliveryRow.session_id == sid).with_for_update()
            )
            assert delivery is not None
            row = await db.get(SessionRow, sid)
            assert row is not None
            if delivery.provider_id:
                _erase_local_recipient(row)
                return str(delivery.provider_id)
            created = (
                delivery.created_at.replace(tzinfo=UTC)
                if delivery.created_at.tzinfo is None
                else delivery.created_at
            )
            if datetime.now(UTC) - created >= timedelta(hours=23):
                raise ApplicationError("Email outcome requires reconciliation", non_retryable=True)
            if row.deleted_at:
                raise ApplicationError("Session is deleted", non_retryable=True)
            delivery.attempts += 1
            if settings.email_mode == "preview":
                folder = Path(".data/email-previews")
                await asyncio.to_thread(folder.mkdir, parents=True, exist_ok=True)
                await asyncio.to_thread((folder / f"{sid}.html").write_text, payload["html"])
                provider_id = f"preview-{sid}"
            else:
                if not settings.resend_api_key.get_secret_value() or not settings.resend_from_email:
                    raise ApplicationError("Resend credentials are missing", non_retryable=True)
                if not delivery.payload.get("from"):
                    raise ApplicationError("Frozen email sender is missing", non_retryable=True)
                provider_id = await send(
                    settings.resend_api_key.get_secret_value(),
                    {
                        **delivery.payload,
                        "to": [repo.cipher.decrypt(row.encrypted_email).decode()],
                    },
                    f"final-itinerary/{sid}",
                )
            delivery.provider_id, delivery.status = provider_id, "submitted"
            _erase_local_recipient(row)
            return provider_id
