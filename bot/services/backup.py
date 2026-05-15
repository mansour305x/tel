import shutil
from datetime import datetime
from pathlib import Path


def create_backup(main_path: Path, db_path: Path, backup_root: Path) -> Path:
    backup_dir = backup_root / f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(main_path, backup_dir / main_path.name)
    if db_path.exists():
        shutil.copy2(db_path, backup_dir / db_path.name)
    return backup_dir
