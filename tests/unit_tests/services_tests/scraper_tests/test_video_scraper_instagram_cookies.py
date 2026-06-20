from types import SimpleNamespace

import pytest

from mealie.services.scraper import scraper_strategies
from mealie.services.scraper.scraper_strategies import RecipeScraperOpenAITranscription


class FakeYoutubeDL:
    captured_opts: list[dict] = []

    def __init__(self, opts: dict) -> None:
        self.captured_opts.append(opts)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, url: str, download: bool):
        return {"title": "Test", "description": "Description", "thumbnail": None}


def scraper(url: str) -> RecipeScraperOpenAITranscription:
    return RecipeScraperOpenAITranscription(url, translator=object(), repos=object())


@pytest.fixture(autouse=True)
def fake_youtube_dl(monkeypatch: pytest.MonkeyPatch):
    FakeYoutubeDL.captured_opts = []
    monkeypatch.setattr(scraper_strategies.yt_dlp, "YoutubeDL", FakeYoutubeDL)


@pytest.mark.parametrize(
    ("url", "uses_cookies"),
    [
        ("https://www.instagram.com/reel/abc123/", True),
        ("https://instagram.com/reels/abc123/", True),
        ("https://www.youtube.com/watch?v=abc123", False),
    ],
)
def test_instagram_cookies_file_is_only_passed_to_instagram_urls(
    monkeypatch: pytest.MonkeyPatch, tmp_path, url, uses_cookies
):
    cookies_file = tmp_path / "instagram.cookies.txt"
    cookies_file.write_text("# Netscape HTTP Cookie File\n")
    monkeypatch.setattr(
        scraper_strategies,
        "get_app_settings",
        lambda: SimpleNamespace(INSTAGRAM_COOKIES_FILE=str(cookies_file)),
    )

    scraper(url)._download_audio(tmp_path)

    opts = FakeYoutubeDL.captured_opts[-1]
    assert ("cookiefile" in opts) is uses_cookies
    if uses_cookies:
        assert opts["cookiefile"] == str(cookies_file)


def test_empty_instagram_cookies_file_setting_is_ignored(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr(
        scraper_strategies,
        "get_app_settings",
        lambda: SimpleNamespace(INSTAGRAM_COOKIES_FILE=None),
    )

    scraper("https://www.instagram.com/reel/abc123/")._download_audio(tmp_path)

    opts = FakeYoutubeDL.captured_opts[-1]
    assert "cookiefile" not in opts
