"""Tests for auth/browser_cookies.py helpers."""

from authsome.auth.browser_cookies import cookies_are_valid, normalize_jsessionid


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
