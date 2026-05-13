"""Shared utility functions for the auth module."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import urlsplit, urlunsplit

from authsome.server.urls import DEFAULT_SERVER_BASE_URL, build_callback_url

if TYPE_CHECKING:
    from authsome.auth.sessions import AuthSession

_DEFAULT_CALLBACK_URL = build_callback_url(DEFAULT_SERVER_BASE_URL)


def resolve_callback_url(runtime_session: AuthSession) -> str:
    """Resolve the callback URL."""
    callback_override = runtime_session.payload.get("callback_url_override")
    if callback_override:
        return str(callback_override)

    return _DEFAULT_CALLBACK_URL


def normalize_scopes(scopes: list[str] | None) -> set[str]:
    """Normalize a list of scopes into a set of cleaned strings."""
    return {scope.strip() for scope in scopes or [] if scope.strip()}


def normalize_base_url(base_url: str | None) -> str | None:
    """Normalize a base URL, enforcing lowercase scheme and host, and removing trailing slash."""
    if not base_url:
        return None
    raw = base_url.strip().rstrip("/")
    parsed = urlsplit(raw)
    if not parsed.scheme or not parsed.netloc:
        return raw
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            parsed.query,
            parsed.fragment,
        )
    )


def export_name_part(value: str) -> str:
    """Convert a string into a component suitable for an environment variable name."""
    return re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")
