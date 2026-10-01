import asyncio

from alembic import context
from sqlalchemy.engine import Connection

from cpfc_trip.config import Settings
from cpfc_trip.persistence.database import engine
from cpfc_trip.persistence.models import Base


def migrate(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def online() -> None:
    db = engine(Settings())
    async with db.connect() as connection:
        await connection.run_sync(migrate)
    await db.dispose()


asyncio.run(online())
