from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Iterable

from bot.exceptions.errors import ValidationError


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w\-. ]+", "", name).strip()
    cleaned = re.sub(r"[\s]+", " ", cleaned)
    if not cleaned:
        raise ValidationError("لم يتم العثور على اسم ملف صالح.")
    return cleaned[:120]


def ensure_directories(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def safe_path(base_dir: Path, file_name: str) -> Path:
    candidate = (base_dir / file_name).resolve()
    if not candidate.exists() and not str(candidate).startswith(str(base_dir.resolve())):
        raise ValidationError("محاولة وصول إلى مسار غير مصرح به.")
    return candidate


def cleanup_files(paths: Iterable[Path]) -> None:
    for item in paths:
        try:
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            elif item.exists():
                item.unlink()
        except OSError:
            continue
