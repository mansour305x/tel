from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.models.setting import Setting
from bot.database.session import create_async_session


class SettingsService:
    DEFAULTS = {
        "max_file_size_mb": "50",
        "default_quality": "best",
        "workers_count": "2",
        "rate_limit": "3",
        "retention_seconds": "3600",
    }

    def __init__(self, database_url: str) -> None:
        self.session_maker = create_async_session(database_url)

    async def initialize(self) -> None:
        async with self.session_maker() as session:
            for key, value in self.DEFAULTS.items():
                result = await session.execute(select(Setting).where(Setting.key == key))
                if not result.scalar_one_or_none():
                    session.add(Setting(key=key, value=value))
            await session.commit()

    async def get(self, key: str) -> str | None:
        async with self.session_maker() as session:
            result = await session.execute(select(Setting).where(Setting.key == key))
            setting = result.scalar_one_or_none()
            return setting.value if setting else self.DEFAULTS.get(key)

    async def set(self, key: str, value: str) -> None:
        async with self.session_maker() as session:
            result = await session.execute(select(Setting).where(Setting.key == key))
            setting = result.scalar_one_or_none()
            if setting:
                setting.value = value
            else:
                session.add(Setting(key=key, value=value))
            await session.commit()

    async def all(self) -> dict[str, str]:
        async with self.session_maker() as session:
            result = await session.execute(select(Setting))
            return {setting.key: setting.value for setting in result.scalars().all()}
