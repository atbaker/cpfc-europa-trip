"""DigitalOcean provides a PostgreSQL URL without SQLAlchemy's async driver."""

from cpfc_trip.config import Settings
from cpfc_trip.persistence.database import engine


def test_digitalocean_postgresql_url_uses_asyncpg_and_tls(settings: Settings) -> None:
    database = engine(
        settings.model_copy(
            update={
                "database_url": "postgresql://user:password@db.example:25060/defaultdb?sslmode=require"
            }
        )
    )
    try:
        assert database.url.drivername == "postgresql+asyncpg"
        assert database.url.query == {"ssl": "require"}
    finally:
        database.sync_engine.dispose(close=False)
