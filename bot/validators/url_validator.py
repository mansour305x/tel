from __future__ import annotations

import re
from urllib.parse import urlparse

from bot.exceptions.errors import UnsupportedPlatformError, ValidationError

SUPPORTED_DOMAINS = {
    "youtube": [r"(^|\.)youtube\.com$", r"(^|\.)youtu\.be$"],
    "tiktok": [r"(^|\.)tiktok\.com$"],
    "instagram": [r"(^|\.)instagram\.com$"],
    "snapchat": [r"(^|\.)snapchat\.com$", r"(^|\.)snapchat\.com$"],
}

PLATFORM_LABELS = {
    "youtube": "YouTube",
    "tiktok": "TikTok",
    "instagram": "Instagram",
    "snapchat": "Snapchat",
}


def validate_url(url: str) -> str:
    if not url or not isinstance(url, str):
        raise ValidationError("الرابط غير صالح.")

    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValidationError("الرابط يجب أن يبدأ بـ https:// أو http://.")

    if parsed.netloc.lower().endswith(".exe"):
        raise ValidationError("الرابط يحتوي على محتوى مريب.")

    return url.strip()


def detect_platform(url: str) -> str:
    parsed = urlparse(url)
    hostname = parsed.hostname or ""
    for platform, patterns in SUPPORTED_DOMAINS.items():
        for pattern in patterns:
            if re.search(pattern, hostname, flags=re.IGNORECASE):
                return platform
    raise UnsupportedPlatformError("المنصة غير مدعومة في الوقت الحالي.")


def format_platform(platform: str) -> str:
    return PLATFORM_LABELS.get(platform, platform.capitalize())
