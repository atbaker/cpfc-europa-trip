"""Delete expired personal data from the application database."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from cpfc_trip.config import Settings
from cpfc_trip.persistence.database import engine
from cpfc_trip.persistence.models import DeliveryRow, SessionRow, WebhookRow

RETENTION_DAYS = 30


async def prune_expired(
    sessions: async_sessionmaker[AsyncSession], *, now: datetime | None = None
) -> tuple[int, int, int]:
    cutoff = (now or datetime.now(UTC)) - timedelta(days=RETENTION_DAYS)
    async with sessions.begin() as db:
        deliveries = await db.execute(
            delete(DeliveryRow).where(
                DeliveryRow.session_id.in_(
                    select(SessionRow.id).where(SessionRow.created_at < cutoff)
                )
            )
        )
        session_rows = await db.execute(delete(SessionRow).where(SessionRow.created_at < cutoff))
        webhooks = await db.execute(delete(WebhookRow).where(WebhookRow.received_at < cutoff))
    return (
        cast(CursorResult[Any], deliveries).rowcount,
        cast(CursorResult[Any], session_rows).rowcount,
        cast(CursorResult[Any], webhooks).rowcount,
    )


async def _run() -> None:
    database = engine(Settings())
    try:
        counts = await prune_expired(async_sessionmaker(database))
        print(
            f"Expired rows deleted: deliveries={counts[0]} sessions={counts[1]} webhooks={counts[2]}"
        )
    finally:
        await database.dispose()


def main() -> None:
    asyncio.run(_run())
