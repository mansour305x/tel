import asyncio
import os
import sys
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message

BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_NAME = os.getenv("BOT_NAME", "child_bot")

if not BOT_TOKEN:
    raise SystemExit("BOT_TOKEN غير موجود للبوت الفرعي")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(message: Message) -> None:
    await message.answer(f"✅ {BOT_NAME} يعمل بنجاح.")


@dp.message()
async def echo(message: Message) -> None:
    await message.answer("🔔 هذه بوت فرعي تجريبي. أرسل /start لمعرفة الحالة.")


async def main() -> None:
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
