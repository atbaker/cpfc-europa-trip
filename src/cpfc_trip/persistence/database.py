from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from cpfc_trip.config import Settings


def engine(settings: Settings) -> AsyncEngine:
    url = make_url(settings.database_url)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+asyncpg")
    sslmode = url.query.get("sslmode")
    if isinstance(sslmode, str) and url.drivername == "postgresql+asyncpg":
        url = url.difference_update_query(["sslmode"]).update_query_dict({"ssl": sslmode})
    return create_async_engine(url, pool_pre_ping=True)
