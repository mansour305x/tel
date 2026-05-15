import asyncio
import importlib
import inspect
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from dotenv import load_dotenv


load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN غير موجود داخل ملف .env")


HANDLER_MODULES = [
    "bot.handlers.user",
    "bot.handlers.owner",
    "bot.handlers.builder",
    "bot.handlers.projects",
    "bot.handlers.support",
    "bot.handlers.broadcast",
]


async def maybe_await(result):
    if inspect.isawaitable(result):
        return await result
    return result


async def init_database_if_exists():
    try:
        database = importlib.import_module("bot.database")
    except Exception:
        return

    for fn_name in ("init_db", "init_database", "setup_database", "setup_db"):
        fn = getattr(database, fn_name, None)
        if fn:
            await maybe_await(fn())
            logging.info("Database initialized using %s", fn_name)
            return


async def register_handlers(dp: Dispatcher, bot: Bot):
    loaded = 0

    for module_name in HANDLER_MODULES:
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            logging.warning("Handler module not found: %s", module_name)
            continue

        router = getattr(module, "router", None)
        if router is not None:
            dp.include_router(router)
            loaded += 1
            logging.info("Included router from %s", module_name)
            continue

        for fn_name in ("register", "setup", "register_handlers"):
            fn = getattr(module, fn_name, None)
            if not fn:
                continue

            try:
                sig = inspect.signature(fn)
                params = list(sig.parameters.keys())

                kwargs = {}
                if "dp" in params:
                    kwargs["dp"] = dp
                if "dispatcher" in params:
                    kwargs["dispatcher"] = dp
                if "bot" in params:
                    kwargs["bot"] = bot

                if kwargs:
                    await maybe_await(fn(**kwargs))
                elif len(params) == 0:
                    await maybe_await(fn())
                elif len(params) == 1:
                    await maybe_await(fn(dp))
                else:
                    await maybe_await(fn(dp, bot))

                loaded += 1
                logging.info("Registered handlers from %s using %s", module_name, fn_name)
                break

            except Exception as e:
                logging.exception("Failed registering %s: %s", module_name, e)

    if loaded == 0:
        logging.warning("No routers or handlers were registered.")


async def main():
    await init_database_if_exists()

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()

    await register_handlers(dp, bot)

    await bot.delete_webhook(drop_pending_updates=True)

    print("Mansour Factory Bot V6 Builder is running...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
