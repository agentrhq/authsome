"""Helpers for resolving the daemon's external URLs."""

from urllib.parse import urlencode

from authsome.server.config import get_server_config

# Invariant: must match the OAuth callback route declared in routes/auth.py.
DEFAULT_CALLBACK_PATH = "/api/auth/callback/oauth"


def build_server_base_url() -> str:
    """Return the canonical external base URL for the daemon."""
    return get_server_config().base_url


def _base_url(base_url: str | None = None) -> str:
    return (base_url or get_server_config().base_url).rstrip("/")


def build_callback_url(base_url: str | None = None) -> str:
    """Return the OAuth callback URL for the daemon."""
    return f"{_base_url(base_url)}{DEFAULT_CALLBACK_PATH}"


def build_auth_input_url(base_url: str, session_id: str) -> str:
    """Return the browser input page URL for a session."""
    return f"{_base_url(base_url)}/auth/input?session={session_id}"


def build_auth_success_url(base_url: str, session_id: str) -> str:
    """Return the browser success page URL for a session."""
    return f"{_base_url(base_url)}/auth/success?{urlencode({'session': session_id})}"


def build_device_url(base_url: str, session_id: str) -> str:
    """Return the browser device-code page URL for a session."""
    return f"{_base_url(base_url)}/auth/device?session={session_id}"
