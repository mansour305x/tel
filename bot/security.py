import html
import re
from pathlib import Path

from bot.validator import VALID_ACTION_TYPES, VALID_CATEGORIES, VALID_LOCATIONS

MAX_KEY_LENGTH = 32
MAX_LABEL_LENGTH = 64
MAX_TEXT_LENGTH = 512
MAX_URL_LENGTH = 256

INVALID_KEY_PATTERN = re.compile(r"[^a-z0-9_\-]")


def sanitize_text(value: str) -> str:
    return html.escape(value.strip(), quote=False)


def validate_template_key(key: str) -> str:
    key = key.strip().lower()
    if not key:
        raise ValueError("مفتاح القالب لا يمكن أن يكون فارغًا.")
    if len(key) > MAX_KEY_LENGTH:
        raise ValueError("المفتاح طويل جدًا.")
    if INVALID_KEY_PATTERN.search(key):
        raise ValueError("المفتاح يجب أن يحتوي على أحرف صغيرة وأرقام و_ فقط.")
    if key in {"admin", "owner", "support", "settings", "templates"}:
        raise ValueError("المفتاح محجوز ويجب تغييره.")
    return key


def validate_label(label: str) -> str:
    label = label.strip()
    if not label:
        raise ValueError("اسم الزر أو القالب لا يمكن أن يكون فارغًا.")
    if len(label) > MAX_LABEL_LENGTH:
        raise ValueError("الاسم طويل جدًا.")
    return sanitize_text(label)


def validate_description(description: str) -> str:
    description = description.strip()
    if not description:
        raise ValueError("الوصف لا يمكن أن يكون فارغًا.")
    if len(description) > MAX_TEXT_LENGTH:
        raise ValueError("الوصف طويل جدًا.")
    return sanitize_text(description)


def validate_category(category: str) -> str:
    category = category.strip()
    if category not in VALID_CATEGORIES:
        raise ValueError("نوع القالب غير صالح.")
    return category


def validate_location(location: str) -> str:
    location = location.strip()
    if location not in VALID_LOCATIONS:
        raise ValueError("مكان الزر غير صالح.")
    return location


def validate_action_type(action_type: str) -> str:
    action_type = action_type.strip()
    if action_type not in VALID_ACTION_TYPES:
        raise ValueError("نوع الوظيفة غير صالح.")
    return action_type


def validate_url(target: str) -> str:
    target = target.strip()
    if len(target) > MAX_URL_LENGTH:
        raise ValueError("الرابط طويل جدًا.")
    if not target.startswith(("http://", "https://")):
        raise ValueError("الرابط يجب أن يبدأ بـ http:// أو https://.")
    return sanitize_text(target)


def validate_action_value(action_type: str, action_value: str) -> str:
    action_type = validate_action_type(action_type)
    raw = action_value.strip()
    if action_type == "url":
        return validate_url(raw)
    if action_type in {"message", "template", "support", "stats", "broadcast", "setting_toggle"}:
        if not raw:
            raise ValueError("محتوى الوظيفة لا يمكن أن يكون فارغًا.")
        if len(raw) > MAX_TEXT_LENGTH:
            raise ValueError("محتوى الوظيفة طويل جدًا.")
        return sanitize_text(raw)
    if action_type in {"project_start", "project_stop", "project_restart"}:
        if not raw.isdigit():
            raise ValueError("معرّف المشروع يجب أن يكون رقماً صالحًا.")
        return raw
    if action_type == "menu":
        if raw not in VALID_LOCATIONS:
            raise ValueError("القائمة المرتبطة غير صالحة.")
        return raw
    raise ValueError("نوع الوظيفة غير مدعوم.")
