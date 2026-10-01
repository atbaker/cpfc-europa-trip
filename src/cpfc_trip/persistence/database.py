from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from cpfc_trip.config import Settings


def engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(settings.database_url, pool_pre_ping=True)
