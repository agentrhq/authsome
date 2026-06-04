"""Filesystem layout helpers for Authsome."""

from pathlib import Path

from authsome.config import get_authsome_config


def get_authsome_home(home: Path | None = None) -> Path:
    """Return the root Authsome home directory."""
    return get_authsome_config(home).home


def get_client_home(home: Path | None = None) -> Path:
    """Return the client-owned Authsome directory."""
    return get_authsome_config(home).client_home


def get_server_home(home: Path | None = None) -> Path:
    """Return the server-owned Authsome directory."""
    return get_authsome_config(home).server_home


def get_client_log_path(home: Path | None = None) -> Path:
    """Return the default client log file path."""
    return get_authsome_config(home).client_log_path


def get_server_log_path(home: Path | None = None) -> Path:
    """Return the default server log file path."""
    return get_authsome_config(home).server_log_path
