import asyncio
from pathlib import Path

from bot.config import BotConfig
from bot.downloader.yt_downloader import YoutubeDownloader


def test_youtube_downloader_extract_info(monkeypatch):
    config = BotConfig(
        bot_token="token",
        admin_ids=[],
        max_file_size_mb=50,
        download_dir=Path("downloads"),
        temp_dir=Path("temp"),
        cookies_file=None,
        rate_limit=3,
        workers_count=1,
        default_quality="best",
        retention_seconds=3600,
        database_url="sqlite+aiosqlite:///./test.db",
        log_level="INFO",
    )
    downloader = YoutubeDownloader(config)

    def fake_extract_info(url):
        return {"title": "Test Video", "ext": "mp4"}

    monkeypatch.setattr(downloader, "_extract_info_sync", fake_extract_info)

    result = asyncio.run(downloader.extract_info("https://test.url"))
    assert result["title"] == "Test Video"


def test_youtube_downloader_download_creates_file(monkeypatch, tmp_path: Path):
    config = BotConfig(
        bot_token="token",
        admin_ids=[],
        max_file_size_mb=50,
        download_dir=tmp_path / "downloads",
        temp_dir=tmp_path / "temp",
        cookies_file=None,
        rate_limit=3,
        workers_count=1,
        default_quality="best",
        retention_seconds=3600,
        database_url="sqlite+aiosqlite:///./test.db",
        log_level="INFO",
    )
    downloader = YoutubeDownloader(config)

    def fake_extract_info(url):
        return {"title": "Test Video", "ext": "mp4"}

    def fake_download_sync(url, quality, output_template):
        output_template.parent.mkdir(parents=True, exist_ok=True)
        file_path = Path(str(output_template).replace("%(ext)s", "mp4"))
        file_path.write_text("data")

    monkeypatch.setattr(downloader, "_extract_info_sync", fake_extract_info)
    monkeypatch.setattr(downloader, "_download_sync", fake_download_sync)

    result = asyncio.run(downloader.download("https://test.url", "best", tmp_path))
    assert result.exists()
    assert result.suffix == ".mp4"
