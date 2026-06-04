"""Backward-compatible server settings imports."""

from __future__ import annotations

from authsome.server.config import ServerConfig as ServerSettings
from authsome.server.config import get_server_config


def get_settings() -> ServerSettings:
    """Return daemon runtime settings."""
    return get_server_config()


__all__ = ["ServerSettings", "get_settings"]
