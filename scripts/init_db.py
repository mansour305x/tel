from bot.config import BotConfig
from bot.database.setup import initialize_database


async def main() -> None:
    config = BotConfig()
    await initialize_database(config.database_url)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
