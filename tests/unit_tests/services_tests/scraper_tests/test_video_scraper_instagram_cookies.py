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
    ("url", "expected_cookiefile"),
    [
        ("https://www.instagram.com/reel/abc123/", "instagram"),
        ("https://instagram.com/reels/abc123/", "instagram"),
        ("https://www.youtube.com/watch?v=abc123", "youtube"),
        ("https://youtu.be/abc123", "youtube"),
        ("https://www.example.com/video/abc123", None),
    ],
)
def test_social_cookie_file_is_passed_to_matching_platform(
    monkeypatch: pytest.MonkeyPatch, tmp_path, url, expected_cookiefile
):
    instagram_cookies_file = tmp_path / "instagram.cookies.txt"
    youtube_cookies_file = tmp_path / "youtube.cookies.txt"
    instagram_cookies_file.write_text("# Netscape HTTP Cookie File\n")
    youtube_cookies_file.write_text("# Netscape HTTP Cookie File\n")
    monkeypatch.setattr(
        scraper_strategies,
        "get_app_settings",
        lambda: SimpleNamespace(
            INSTAGRAM_COOKIES_FILE=str(instagram_cookies_file),
            YOUTUBE_COOKIES_FILE=str(youtube_cookies_file),
        ),
    )

    scraper(url)._download_audio(tmp_path)

    opts = FakeYoutubeDL.captured_opts[-1]
    if expected_cookiefile == "instagram":
        assert opts["cookiefile"] == str(instagram_cookies_file)
    elif expected_cookiefile == "youtube":
        assert opts["cookiefile"] == str(youtube_cookies_file)
    else:
        assert "cookiefile" not in opts


def test_empty_social_cookies_file_settings_are_ignored(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr(
        scraper_strategies,
        "get_app_settings",
        lambda: SimpleNamespace(INSTAGRAM_COOKIES_FILE=None, YOUTUBE_COOKIES_FILE=None),
    )

    scraper("https://www.instagram.com/reel/abc123/")._download_audio(tmp_path)

    opts = FakeYoutubeDL.captured_opts[-1]
    assert "cookiefile" not in opts


def test_youtube_subtitles_are_used_before_video_download(monkeypatch: pytest.MonkeyPatch, tmp_path):
    class SubtitleYoutubeDL:
        captured_opts: list[dict] = []

        def __init__(self, opts: dict) -> None:
            self.captured_opts.append(opts)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, url: str, download: bool):
            if download:
                (tmp_path / "mealie.en-orig.vtt").write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\none cup sugar\n")
            return {
                "title": "Recipe Short",
                "description": "Short description",
                "thumbnail": "https://example.com/thumb.jpg",
                "automatic_captions": {"en-orig": [{}]},
                "subtitles": {},
            }

    monkeypatch.setattr(scraper_strategies.yt_dlp, "YoutubeDL", SubtitleYoutubeDL)
    monkeypatch.setattr(
        scraper_strategies,
        "get_app_settings",
        lambda: SimpleNamespace(INSTAGRAM_COOKIES_FILE=None, YOUTUBE_COOKIES_FILE=None),
    )

    video_data = scraper("https://www.youtube.com/shorts/abc123")._download_audio(tmp_path)

    assert video_data["subtitle"] == tmp_path / "mealie.en-orig.vtt"
    assert video_data["title"] == "Recipe Short"
    assert all("format" not in opts for opts in SubtitleYoutubeDL.captured_opts)
