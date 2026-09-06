"""Async SQLAlchemy engine construction."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from cpfc_trip.config import get_settings


@lru_cache
def engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, pool_pre_ping=True, pool_size=5)


@lru_cache
def session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine(), expire_on_commit=False)
