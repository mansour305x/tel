from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from pydantic import BaseSettings, Field, validator


class BotConfig(BaseSettings):
    bot_token: str = Field(..., env="BOT_TOKEN")
    admin_ids: List[int] = Field(default_factory=list, env="ADMIN_IDS")
    max_file_size_mb: int = Field(50, env="MAX_FILE_SIZE_MB")
    download_dir: Path = Field(Path("downloads"), env="DOWNLOAD_DIR")
    temp_dir: Path = Field(Path("temp"), env="TEMP_DIR")
    cookies_file: Optional[Path] = Field(None, env="COOKIES_FILE")
    rate_limit: int = Field(3, env="RATE_LIMIT")
    workers_count: int = Field(2, env="WORKERS_COUNT")
    default_quality: str = Field("best", env="DEFAULT_QUALITY")
    retention_seconds: int = Field(3600, env="RETENTION_SECONDS")
    database_url: str = Field("sqlite+aiosqlite:///./data/bot.db", env="DATABASE_URL")
    log_level: str = Field("INFO", env="LOG_LEVEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @validator("admin_ids", pre=True)
    def parse_admin_ids(cls, value: str | List[int]) -> List[int]:
        if isinstance(value, list):
            return value
        if not value:
            return []
        return [int(item.strip()) for item in str(value).split(",") if item.strip().isdigit()]

    @validator("download_dir", "temp_dir", "cookies_file", pre=True)
    def normalize_paths(cls, value: str | Path | None) -> Optional[Path]:
        if value is None or value == "":
            return None
        return Path(value)

    def ensure_directories(self) -> None:
        for path in [self.download_dir, self.temp_dir, Path("logs"), Path("data")]:
            if path is not None:
                path.mkdir(parents=True, exist_ok=True)
