from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


def create_async_session(database_url: str) -> sessionmaker[AsyncSession]:
    engine: AsyncEngine = create_async_engine(
        database_url,
        future=True,
        echo=False,
        connect_args={"check_same_thread": False},
    )
    return sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
