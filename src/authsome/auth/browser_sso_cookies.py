"""Shared helpers for normalizing browser SSO credential dicts."""

from __future__ import annotations

import re

_JSESSIONID_IN_COOKIE = re.compile(r'JSESSIONID="?([^";]+)"?')


def normalize_browser_sso_credentials(credentials: dict[str, str]) -> dict[str, str]:
    """Return a copy with site-specific cookie fixes applied.

    LinkedIn requires ``JSESSIONID="ajax:…"`` in the ``Cookie`` header and a
    bare ``ajax:…`` value in ``csrf-token``.  Playwright extraction can leave
    the csrf token only inside the cookie blob — derive it when missing.
    """
    normalized = dict(credentials)
    jsessionid = normalized.get("jsessionid")
    if jsessionid:
        normalized["jsessionid"] = jsessionid.strip().strip('"')
    else:
        match = _JSESSIONID_IN_COOKIE.search(normalized.get("cookie", ""))
        if match:
            normalized["jsessionid"] = match.group(1)
    return normalized
