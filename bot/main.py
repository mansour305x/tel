import asyncio
import logging

from aiogram import Application
from aiogram.enums import ParseMode

from bot.config import BotConfig
from bot.database import initialize_database
from bot.handlers import register_handlers


def create_application() -> Application:
    config = BotConfig()
    config.ensure_directories()
    logging.basicConfig(level=getattr(logging, config.log_level, logging.INFO))

    app = Application.builder().token(config.bot_token).parse_mode(ParseMode.HTML).build()
    for router in register_handlers():
        app.include_router(router)

    @app.startup
    async def on_startup() -> None:
        await initialize_database(config)

    return app


def main() -> None:
    app = create_application()
    app.run_polling()


if __name__ == "__main__":
    main()
