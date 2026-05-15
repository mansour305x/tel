#!/usr/bin/env bash
set -e
python -c "from bot.services.updater import publish_update; import asyncio; from bot.config import BotConfig; print(asyncio.run(publish_update(BotConfig(), ['main.py', 'requirements.txt', '.gitignore'])))"
