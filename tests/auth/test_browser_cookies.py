"""Tests for auth/browser_cookies.py helpers."""

from authsome.auth.browser_cookies import COOKIE_EXPIRES_AT_KEY, cookies_are_valid, normalize_jsessionid


def test_cookies_valid_when_all_present():
    assert cookies_are_valid({"auth_token": "tok123", "ct0": "csrf"}, ["auth_token"]) is True


def test_cookies_invalid_when_required_missing():
    assert cookies_are_valid({"ct0": "csrf"}, ["auth_token"]) is False


def test_cookies_invalid_when_empty_string():
    assert cookies_are_valid({"auth_token": ""}, ["auth_token"]) is False


def test_cookies_invalid_when_whitespace_only():
    assert cookies_are_valid({"auth_token": "   "}, ["auth_token"]) is False


def test_cookies_valid_multiple_required():
    assert cookies_are_valid({"li_at": "tok", "JSESSIONID": "ajax:1"}, ["li_at", "JSESSIONID"]) is True


def test_cookies_invalid_partial():
    assert cookies_are_valid({"li_at": "tok"}, ["li_at", "JSESSIONID"]) is False


def test_normalize_jsessionid_strips_quotes():
    result = normalize_jsessionid({"JSESSIONID": '"ajax:12345"'})
    assert result["JSESSIONID"] == "ajax:12345"


def test_normalize_jsessionid_noop_when_no_quotes():
    result = normalize_jsessionid({"JSESSIONID": "ajax:12345"})
    assert result["JSESSIONID"] == "ajax:12345"


def test_normalize_jsessionid_leaves_other_cookies_unchanged():
    result = normalize_jsessionid({"JSESSIONID": '"val"', "li_at": "token"})
    assert result["li_at"] == "token"


def test_normalize_jsessionid_noop_when_key_absent():
    result = normalize_jsessionid({"li_at": "token"})
    assert "JSESSIONID" not in result
    assert result["li_at"] == "token"


def test_read_chrome_cookies_attaches_ttl_from_cookie(monkeypatch):
    import sys

    from authsome.auth import browser_cookies as mod

    class FakeCookie:
        def __init__(self, domain: str, name: str, value: str, expires: int | None) -> None:
            self.domain = domain
            self.name = name
            self.value = value
            self.expires = expires

    class FakeJar:
        def __iter__(self):
            yield FakeCookie(".www.linkedin.com", "li_at", "token", 1_800_000_000)
            yield FakeCookie(".www.linkedin.com", "bcookie", "other", 1_800_000_000)

    monkeypatch.setitem(sys.modules, "browser_cookie3", type("M", (), {"chrome": staticmethod(lambda: FakeJar())}))
    monkeypatch.setattr(mod.time, "time", lambda: 1_700_000_000)

    result = mod.read_chrome_cookies([".linkedin.com"], ttl_from_cookie="li_at")

    assert result["li_at"] == "token"
    assert result[COOKIE_EXPIRES_AT_KEY] == "1800000000"


def test_read_chrome_cookies_omits_expiry_when_ttl_cookie_is_session(monkeypatch):
    import sys

    from authsome.auth import browser_cookies as mod

    class FakeCookie:
        def __init__(self, domain: str, name: str, value: str, expires: int | None) -> None:
            self.domain = domain
            self.name = name
            self.value = value
            self.expires = expires

    class FakeJar:
        def __iter__(self):
            yield FakeCookie(".www.linkedin.com", "li_at", "token", None)

    monkeypatch.setitem(sys.modules, "browser_cookie3", type("M", (), {"chrome": staticmethod(lambda: FakeJar())}))
    monkeypatch.setattr(mod.time, "time", lambda: 1_700_000_000)

    result = mod.read_chrome_cookies([".linkedin.com"], ttl_from_cookie="li_at")

    assert result["li_at"] == "token"
    assert COOKIE_EXPIRES_AT_KEY not in result
