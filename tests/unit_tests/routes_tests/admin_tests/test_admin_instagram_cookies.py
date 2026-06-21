import subprocess

from mealie.routes.admin.admin_debug import AdminDebugController


def test_instagram_cookie_validation_accepts_netscape_instagram_cookie():
    text = "# Netscape HTTP Cookie File\n.instagram.com\tTRUE\t/\tTRUE\t1893456000\tsessionid\tredacted\n"

    assert AdminDebugController._inspect_cookie_text(text) == (True, True)


def test_instagram_cookie_validation_rejects_non_instagram_cookie():
    text = "# Netscape HTTP Cookie File\n.example.com\tTRUE\t/\tTRUE\t1893456000\tsessionid\tredacted\n"

    assert AdminDebugController._inspect_cookie_text(text) == (True, False)


def test_instagram_cookie_validation_rejects_domain_containing_instagram_name():
    text = "# Netscape HTTP Cookie File\n.notinstagram.com\tTRUE\t/\tTRUE\t1893456000\tsessionid\tredacted\n"

    assert AdminDebugController._inspect_cookie_text(text) == (True, False)


def test_youtube_cookie_validation_accepts_netscape_youtube_cookie():
    text = "# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t1893456000\tSID\tredacted\n"

    assert AdminDebugController._inspect_cookie_text(text, "youtube.com") == (True, True)


def test_youtube_cookie_validation_rejects_domain_containing_youtube_name():
    text = "# Netscape HTTP Cookie File\n.notyoutube.com\tTRUE\t/\tTRUE\t1893456000\tSID\tredacted\n"

    assert AdminDebugController._inspect_cookie_text(text, "youtube.com") == (True, False)


def test_youtube_cookie_live_check_accepts_ytdlp_success(monkeypatch, tmp_path):
    cookies = tmp_path / "youtube.cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t1893456000\tSID\tredacted\n")

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout="dQw4w9WgXcQ\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert AdminDebugController._youtube_cookie_live_check(cookies) == (
        True,
        "YouTube cookies are uploaded, readable, and accepted by yt-dlp.",
    )


def test_youtube_cookie_live_check_reports_bot_block(monkeypatch, tmp_path):
    cookies = tmp_path / "youtube.cookies.txt"
    cookies.write_text("# Netscape HTTP Cookie File\n.youtube.com\tTRUE\t/\tTRUE\t1893456000\tSID\tredacted\n")

    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args[0],
            1,
            stdout="",
            stderr="ERROR: Sign in to confirm you’re not a bot",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert AdminDebugController._youtube_cookie_live_check(cookies) == (
        False,
        "YouTube cookies are readable, but YouTube still asks for bot/login confirmation.",
    )
