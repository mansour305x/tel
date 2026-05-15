import asyncio
import subprocess
from pathlib import Path
from typing import Sequence

from bot.config import BotConfig


async def run_command(command: Sequence[str], cwd: Path) -> dict[str, str | int]:
    process = await asyncio.create_subprocess_exec(
        *command,
        cwd=str(cwd),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    return {
        "returncode": process.returncode,
        "stdout": stdout.decode().strip(),
        "stderr": stderr.decode().strip(),
    }


async def publish_update(config: BotConfig, safe_files: list[str]) -> dict[str, str | bool]:
    repo_dir = Path(__file__).resolve().parent.parent.parent
    status = await run_command(["git", "status", "--short"], repo_dir)
    if status["returncode"] != 0:
        return {"success": False, "error": "فشل فحص حالة Git."}

    changed_files = status["stdout"].strip()
    if changed_files:
        result = await run_command(["git", "add", *safe_files], repo_dir)
        if result["returncode"] != 0:
            return {"success": False, "error": f"فشل git add: {result['stderr'] or result['stdout']}"}

        commit_msg = "Deploy Mansour Factory V6 Builder"
        result = await run_command(["git", "commit", "-m", commit_msg], repo_dir)
        if result["returncode"] != 0:
            if "nothing to commit" not in (result["stderr"] or result["stdout"]):
                return {"success": False, "error": f"فشل git commit: {result['stderr'] or result['stdout']}"}

    branch = (await run_command(["git", "branch", "--show-current"], repo_dir))["stdout"].strip()
    if not branch:
        return {"success": False, "error": "لم أستطع معرفة الفرع الحالي."}

    result = await run_command(["git", "push", "-u", "origin", branch], repo_dir)
    if result["returncode"] != 0:
        return {"success": False, "error": f"فشل git push: {result['stderr'] or result['stdout']}"}

    return {"success": True, "branch": branch}
