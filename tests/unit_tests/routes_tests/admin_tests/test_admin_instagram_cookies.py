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
