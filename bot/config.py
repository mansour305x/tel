import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv

load_dotenv()


class BotConfig:
    def __init__(self) -> None:
        self.bot_token = os.getenv("BOT_TOKEN", "").strip()
        if not self.bot_token:
            raise ValueError("BOT_TOKEN غير موجود داخل ملف .env")

        owner_id_raw = os.getenv("OWNER_ID", "").strip()
        self.owner_id = int(owner_id_raw) if owner_id_raw.isdigit() else None

        admin_ids_raw = os.getenv("ADMIN_IDS", "").strip()
        self.admin_ids = [int(x.strip()) for x in admin_ids_raw.split(",") if x.strip().isdigit()]
        if self.owner_id and self.owner_id not in self.admin_ids:
            self.admin_ids.append(self.owner_id)

        self.database_path = Path(os.getenv("DATABASE_PATH", "mansour_factory.db")).resolve()
        self.backup_dir = self.database_path.parent / "backups"
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    def ensure_directories(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def is_owner(self, user_id: int) -> bool:
        return self.owner_id is not None and user_id == self.owner_id

    def is_admin(self, user_id: int) -> bool:
        return self.is_owner(user_id) or user_id in self.admin_ids
