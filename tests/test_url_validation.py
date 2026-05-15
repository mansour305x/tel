import pytest

from bot.exceptions.errors import UnsupportedPlatformError, ValidationError
from bot.validators.url_validator import detect_platform, format_platform, validate_url


def test_validate_url_accepts_https():
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert validate_url(url) == url


def test_validate_url_rejects_invalid_scheme():
    with pytest.raises(ValidationError):
        validate_url("ftp://example.com")


def test_detect_platform_youtube():
    assert detect_platform("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "youtube"
    assert format_platform("youtube") == "YouTube"


def test_detect_platform_unsupported():
    with pytest.raises(UnsupportedPlatformError):
        detect_platform("https://example.com/video")
