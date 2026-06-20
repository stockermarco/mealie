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
    ("url", "uses_login"),
    [
        ("https://www.instagram.com/reel/abc123/", True),
        ("https://instagram.com/reels/abc123/", True),
        ("https://www.youtube.com/watch?v=abc123", False),
    ],
)
def test_instagram_login_is_only_passed_to_instagram_urls(monkeypatch: pytest.MonkeyPatch, tmp_path, url, uses_login):
    monkeypatch.setattr(
        scraper_strategies,
        "get_app_settings",
        lambda: SimpleNamespace(INSTAGRAM_USERNAME="tool-user", INSTAGRAM_PASSWORD="tool-password"),
    )

    scraper(url)._download_audio(tmp_path)

    opts = FakeYoutubeDL.captured_opts[-1]
    assert ("username" in opts) is uses_login
    assert ("password" in opts) is uses_login


@pytest.mark.parametrize(
    ("username", "password"),
    [
        (None, "tool-password"),
        ("tool-user", None),
    ],
)
def test_instagram_login_requires_username_and_password(monkeypatch: pytest.MonkeyPatch, tmp_path, username, password):
    monkeypatch.setattr(
        scraper_strategies,
        "get_app_settings",
        lambda: SimpleNamespace(INSTAGRAM_USERNAME=username, INSTAGRAM_PASSWORD=password),
    )

    scraper("https://www.instagram.com/reel/abc123/")._download_audio(tmp_path)

    opts = FakeYoutubeDL.captured_opts[-1]
    assert "username" not in opts
    assert "password" not in opts
