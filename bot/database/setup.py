from __future__ import annotations

from sqlalchemy.ext.asyncio import create_async_engine

from bot.models.base import Base


async def initialize_database(database_url: str) -> None:
    engine = create_async_engine(database_url, future=True, echo=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()
