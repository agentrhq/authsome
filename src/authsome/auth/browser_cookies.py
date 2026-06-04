"""Read cookies from Chrome's on-disk SQLite database via browser-cookie3."""

import time

# Reserved credential key: Unix expiry timestamp for ttl_from_cookie (stripped on resume).
COOKIE_EXPIRES_AT_KEY = "__cookie_expires_at__"


def read_chrome_cookies(
    domains: list[str],
    *,
    ttl_from_cookie: str | None = None,
) -> dict[str, str]:
    """Return a name→value dict of non-expired Chrome cookies matching *domains*.

    When *ttl_from_cookie* is set and that cookie has a server expiry, the result
    also includes ``COOKIE_EXPIRES_AT_KEY`` with its Unix timestamp as a string.

    ``import browser_cookie3`` is lazy so the server process never triggers it.
    Raises ``ImportError`` if browser-cookie3 is not installed.
    """
    import browser_cookie3  # noqa: PLC0415 — intentionally lazy

    jar = browser_cookie3.chrome()
    now = int(time.time())
    result: dict[str, str] = {}
    ttl_expires_at: int | None = None
    for cookie in jar:
        domain = cookie.domain or ""
        normalized = domain.lstrip(".")
        if not any(normalized == d.lstrip(".") or normalized.endswith("." + d.lstrip(".")) for d in domains):
            continue
        if cookie.expires and cookie.expires < now:
            continue
        result[cookie.name] = cookie.value
        if ttl_from_cookie and cookie.name == ttl_from_cookie and cookie.expires:
            ttl_expires_at = int(cookie.expires)
    if ttl_expires_at is not None:
        result[COOKIE_EXPIRES_AT_KEY] = str(ttl_expires_at)
    return result


def cookies_are_valid(cookies: dict[str, str], auth_cookies: list[str]) -> bool:
    """Return True when every required auth cookie is present and non-empty."""
    return all(cookies.get(name, "").strip() for name in auth_cookies)


def normalize_jsessionid(cookies: dict[str, str]) -> dict[str, str]:
    """Strip surrounding quotes from JSESSIONID values.

    browser-cookie3 occasionally returns ``'"ajax:12345..."'`` with literal
    double-quotes from the SQLite row; LinkedIn's API rejects the quoted form.
    """
    result = dict(cookies)
    if "JSESSIONID" in result:
        result["JSESSIONID"] = result["JSESSIONID"].strip('"')
    return result
