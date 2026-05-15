import tempfile
from pathlib import Path

import pytest

from bot.services.settings_service import SettingsService


def test_settings_service_initialize_and_update(tmp_path: Path) -> None:
    db_path = tmp_path / "settings.db"
    service = SettingsService(f"sqlite+aiosqlite:///{db_path}")
    import asyncio

    async def run_test() -> None:
        await service.initialize()
        assert await service.get("max_file_size_mb") == "50"
        await service.set("max_file_size_mb", "100")
        assert await service.get("max_file_size_mb") == "100"

    asyncio.run(run_test())
