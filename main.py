import asyncio
import inspect

from bot.main import main


if name == "__main__":
    result = main()
    if inspect.isawaitable(result):
        asyncio.run(result)
