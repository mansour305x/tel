from __future__ import annotations

import subprocess
from pathlib import Path

from bot.exceptions.errors import DownloadError


def convert_to_mp3(source: Path, target: Path, timeout_seconds: int = 120) -> Path:
    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-vn",
        "-acodec",
        "libmp3lame",
        "-b:a",
        "192k",
        str(target),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, timeout=timeout_seconds)
    except subprocess.CalledProcessError as exc:
        raise DownloadError("فشل تحويل الصوت إلى MP3.") from exc
    except subprocess.TimeoutExpired as exc:
        raise DownloadError("انتهى الوقت أثناء تحويل الملف.") from exc
    return target
