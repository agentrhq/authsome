from authsome.cli.browser_login import (
    PLAYWRIGHT_INSTALL_HINT,
    _credentials_ready_for_validation,
    extract_cookies_from_context,
)


def _make_mock_context(cookies: list[dict]):
    """Build a minimal mock that looks like a Playwright persistent context."""
    from unittest.mock import MagicMock

    ctx = MagicMock()
    ctx.cookies.return_value = cookies
    return ctx


def test_extract_cookies_wildcard_joins_all_domain_matching_cookies():
    """match='*' joins cookies from matching domains as 'k=v; k=v'."""
    ctx = _make_mock_context(
        [
            {"name": "auth_token", "value": "tok123", "domain": "x.com"},
            {"name": "ct0", "value": "abc", "domain": "x.com"},
            {"name": "guest_id", "value": "ggg", "domain": "twitter.com"},
            {"name": "other", "value": "zzz", "domain": "example.com"},  # excluded
        ]
    )
    rules = [{"from": "cookies", "as": "cookie", "match": "*"}]
    result = extract_cookies_from_context(ctx, rules, ["x.com", "twitter.com"])

    assert "cookie" in result
    assert "auth_token=tok123" in result["cookie"]
    assert "ct0=abc" in result["cookie"]
    assert "guest_id=ggg" in result["cookie"]
    assert "other=zzz" not in result["cookie"]


def test_extract_cookies_exact_match_single_value():
    """match='ct0' extracts just the ct0 cookie value."""
    ctx = _make_mock_context(
        [
            {"name": "auth_token", "value": "tok123", "domain": "x.com"},
            {"name": "ct0", "value": "deadbeef", "domain": "x.com"},
        ]
    )
    rules = [{"from": "cookies", "as": "ct0", "match": "ct0"}]
    result = extract_cookies_from_context(ctx, rules, ["x.com"])
    assert result["ct0"] == "deadbeef"


def test_extract_cookies_multiple_rules():
    """Multiple rules can extract different things simultaneously."""
    ctx = _make_mock_context(
        [
            {"name": "auth_token", "value": "tok", "domain": "x.com"},
            {"name": "ct0", "value": "csrf", "domain": "x.com"},
        ]
    )
    rules = [
        {"from": "cookies", "as": "cookie", "match": "*"},
        {"from": "cookies", "as": "ct0", "match": "ct0"},
    ]
    result = extract_cookies_from_context(ctx, rules, ["x.com"])
    assert "cookie" in result
    assert result["ct0"] == "csrf"


def test_extract_cookies_domain_subdomain_match():
    """Subdomain cookies (domain='.x.com') should match against 'x.com'."""
    ctx = _make_mock_context(
        [
            {"name": "auth_token", "value": "tok", "domain": ".x.com"},
        ]
    )
    rules = [{"from": "cookies", "as": "cookie", "match": "*"}]
    result = extract_cookies_from_context(ctx, rules, ["x.com"])
    assert "auth_token=tok" in result.get("cookie", "")


def test_playwright_install_hint_mentions_install():
    assert "install" in PLAYWRIGHT_INSTALL_HINT.lower()
    assert "playwright" in PLAYWRIGHT_INSTALL_HINT.lower()


def test_credentials_ready_requires_named_cookies_not_guest_only():
    """Guest cookies alone must not trigger validation (X auth_token + ct0 required)."""
    rules = [
        {"from": "cookies", "as": "cookie", "match": "*"},
        {"from": "cookies", "as": "ct0", "match": "ct0"},
        {"from": "cookies", "as": "auth_token", "match": "auth_token"},
    ]
    guest_only = {"cookie": "guest_id=abc"}
    assert _credentials_ready_for_validation(guest_only, rules) is False

    logged_in = {"cookie": "auth_token=t; ct0=c", "ct0": "c", "auth_token": "t"}
    assert _credentials_ready_for_validation(logged_in, rules) is True


def test_validate_uses_context_request_not_new_page():
    """Validation must not open/close tabs on the login window."""
    from unittest.mock import MagicMock

    from authsome.cli.browser_login import _validate_credentials_sync

    ctx = MagicMock()
    ctx.request.get.return_value = MagicMock(status=200)

    assert _validate_credentials_sync(
        ctx,
        {"ct0": "x"},
        "https://x.com/i/api/2/notifications/all.json",
        {"x-csrf-token": "x"},
    )
    ctx.request.get.assert_called_once()
    ctx.new_page.assert_not_called()
