"""Shared utility functions for the auth module."""

from __future__ import annotations

import hashlib
import re
import secrets
from base64 import urlsafe_b64encode
from typing import TYPE_CHECKING
from urllib.parse import urlsplit, urlunsplit

if TYPE_CHECKING:
    from authsome.auth.sessions import AuthSession


def generate_pkce() -> tuple[str, str]:
    """Generate code verifier and challenge for PKCE."""
    code_verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def resolve_callback_url(runtime_session: AuthSession) -> str:
    """Return the callback URL injected into the session by the server."""
    return str(runtime_session.payload.get("callback_url_override", ""))


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
