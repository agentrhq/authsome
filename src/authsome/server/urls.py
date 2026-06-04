"""Helpers for resolving the daemon's external URLs."""

from __future__ import annotations

from urllib.parse import urlencode

from authsome.server.config import get_server_config

# Invariant: must match the OAuth callback route declared in routes/auth.py.
DEFAULT_CALLBACK_PATH = "/api/auth/callback/oauth"

# Retained for external importers (proxy, CLI); resolved from server settings.
DEFAULT_SERVER_BASE_URL = get_server_config().resolved_base_url


def build_server_base_url() -> str:
    """Return the canonical external base URL for the daemon."""
    return get_server_config().resolved_base_url


def build_callback_url(base_url: str) -> str:
    """Return the OAuth callback URL for the daemon."""
    return f"{base_url.rstrip('/')}{DEFAULT_CALLBACK_PATH}"


def build_auth_input_url(base_url: str, session_id: str) -> str:
    """Return the browser input page URL for a session."""
    return f"{base_url.rstrip('/')}/auth/input?session={session_id}"


def build_auth_success_url(base_url: str, session_id: str) -> str:
    """Return the browser success page URL for a session."""
    return f"{base_url.rstrip('/')}/auth/success?{urlencode({'session': session_id})}"


def build_device_url(base_url: str, session_id: str) -> str:
    """Return the browser device-code page URL for a session."""
    return f"{base_url.rstrip('/')}/auth/device?session={session_id}"
