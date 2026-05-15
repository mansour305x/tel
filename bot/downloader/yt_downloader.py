from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import yt_dlp

from bot.config import BotConfig
from bot.downloader.ffmpeg_converter import convert_to_mp3
from bot.exceptions.errors import DownloadError
from bot.utils.files import sanitize_filename


class YoutubeDownloader:
    def __init__(self, config: BotConfig) -> None:
        self.config = config

    async def extract_info(self, url: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._extract_info_sync, url)

    def _extract_info_sync(self, url: str) -> dict[str, Any]:
        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "ignoreerrors": False,
            "nocheckcertificate": True,
        }
        if self.config.cookies_file:
            options["cookiefile"] = str(self.config.cookies_file)

        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=False)
            if not info:
                raise DownloadError("فشل جلب معلومات الفيديو.")
            return info

    async def download(self, url: str, quality: str, target_path: Path) -> Path:
        info = await self.extract_info(url)
        filename = sanitize_filename(info.get("title", "download"))
        suffix = ".mp3" if quality == "mp3" else Path(info.get("ext", "mp4")).suffix or ".mp4"
        output_path = target_path / f"{filename}{suffix}"
        temp_path = target_path / f"{filename}.%(ext)s"
        await asyncio.to_thread(self._download_sync, url, quality, temp_path)
        if quality == "mp3":
            audio_source = self._find_downloaded_file(target_path, filename)
            output_path = target_path / f"{filename}.mp3"
            convert_to_mp3(audio_source, output_path)
            audio_source.unlink(missing_ok=True)
        return output_path

    @staticmethod
    def _find_downloaded_file(base_path: Path, base_name: str) -> Path:
        for candidate in base_path.glob(f"{base_name}.*"):
            if candidate.suffix != ".mp3":
                return candidate
        raise DownloadError("لم يتم العثور على الملف بعد التنزيل.")

    def _download_sync(self, url: str, quality: str, output_template: Path) -> None:
        format_option = self._resolve_format(quality)
        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "format": format_option,
            "outtmpl": str(output_template),
            "nocheckcertificate": True,
            "ignoreerrors": False,
        }
        if self.config.cookies_file:
            options["cookiefile"] = str(self.config.cookies_file)
        if quality == "mp3":
            options["extractaudio"] = True
            options["audioformat"] = "mp3"
            options["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}]
        try:
            with yt_dlp.YoutubeDL(options) as downloader:
                downloader.download([url])
        except yt_dlp.utils.DownloadError as exc:
            raise DownloadError("فشل تنزيل الفيديو عبر yt-dlp.") from exc

    @staticmethod
    def _resolve_format(quality: str) -> str:
        if quality == "best":
            return "bestvideo+bestaudio/best"
        if quality == "medium":
            return "best[height<=480]+bestaudio/best"
        if quality == "mp3":
            return "bestaudio/best"
        return "bestvideo+bestaudio/best"
