from __future__ import annotations

import re

from bot.exceptions.errors import ValidationError


def sanitize_qs(value: str) -> str:
    if not isinstance(value, str):
        raise ValidationError("قيمة غير صالحة.")
    cleaned = re.sub(r"[^a-zA-Z0-9_\- ]+", "", value).strip()
    if not cleaned:
        raise ValidationError("القيمة تحتوي على رموز غير مسموح بها.")
    return cleaned
