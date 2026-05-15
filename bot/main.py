from __future__ import annotations

import asyncio
from aiogram import Application
from dotenv import load_dotenv

from bot.config import BotConfig
from bot.database.setup import initialize_database
from bot.handlers.commands import register_handlers
from bot.logger import configure_logging
from bot.services.settings_service import SettingsService
from bot.services.task_manager import TaskManager


def create_application() -> Application:
    load_dotenv()
    config = BotConfig()
    configure_logging(config.log_level)
    config.ensure_directories()
    settings_service = SettingsService(config.database_url)
    task_manager = TaskManager(config, settings_service)

    app = Application.builder().token(config.bot_token).build()
    app.include_router(register_handlers(task_manager, settings_service))

    @app.startup
    async def on_startup() -> None:
        await initialize_database(config.database_url)
        await settings_service.initialize()
        await task_manager.start()

    @app.shutdown
    async def on_shutdown() -> None:
        await task_manager.shutdown()

    return app


def main() -> None:
    app = create_application()
    app.run_polling()


if __name__ == "__main__":
    main()
