"""Read cookies from Chrome's on-disk SQLite database via browser-cookie3."""

from __future__ import annotations

import time


def read_chrome_cookies(domains: list[str]) -> dict[str, str]:
    """Return a name→value dict of non-expired Chrome cookies matching *domains*.

    ``import browser_cookie3`` is lazy so the server process never triggers it.
    Raises ``ImportError`` if browser-cookie3 is not installed.
    """
    import browser_cookie3  # noqa: PLC0415 — intentionally lazy

    jar = browser_cookie3.chrome(domain_name=None)
    now = int(time.time())
    result: dict[str, str] = {}
    for cookie in jar:
        domain = cookie.domain or ""
        normalized = domain.lstrip(".")
        if not any(normalized == d.lstrip(".") or normalized.endswith("." + d.lstrip(".")) for d in domains):
            continue
        if cookie.expires and cookie.expires < now:
            continue
        result[cookie.name] = cookie.value
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
