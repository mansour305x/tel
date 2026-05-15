import asyncio
import os
import signal
import subprocess
from pathlib import Path
from typing import Dict

from bot.config import BotConfig
from bot.database import update_project

PROCESS_REGISTRY: Dict[int, subprocess.Popen] = {}


def _child_runner_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "scripts" / "run_child_bot.py"


async def start_child_bot(project_id: int, bot_token: str, bot_username: str) -> str:
    if project_id in PROCESS_REGISTRY and PROCESS_REGISTRY[project_id].poll() is None:
        return "البوت الفرعي يعمل بالفعل."
    runner = _child_runner_path()
    env = os.environ.copy()
    env["BOT_TOKEN"] = bot_token
    env["BOT_NAME"] = bot_username
    process = subprocess.Popen([os.sys.executable, str(runner)], env=env)
    PROCESS_REGISTRY[project_id] = process
    await update_project(project_id, status="running")
    return "تم بدء تشغيل البوت الفرعي."


async def stop_child_bot(project_id: int) -> str:
    process = PROCESS_REGISTRY.get(project_id)
    if process and process.poll() is None:
        process.send_signal(signal.SIGINT)
        await asyncio.sleep(1)
        if process.poll() is None:
            process.kill()
        PROCESS_REGISTRY.pop(project_id, None)
        await update_project(project_id, status="stopped")
        return "تم إيقاف البوت الفرعي."
    await update_project(project_id, status="stopped")
    return "البوت الفرعي متوقف بالفعل."


async def restart_child_bot(project_id: int, bot_token: str, bot_username: str) -> str:
    await stop_child_bot(project_id)
    return await start_child_bot(project_id, bot_token, bot_username)
