from __future__ import annotations

from pathlib import Path
from loguru import logger


def configure_logging(log_level: str = "INFO") -> None:
    logger.remove()
    log_path = Path("logs") / "bot.log"
    logger.add(
        log_path,
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        level=log_level,
        serialize=False,
        enqueue=True,
    )
    logger.add(
        sink=lambda msg: print(msg, end=""),
        level=log_level,
        colorize=True,
    )
