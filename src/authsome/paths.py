"""Filesystem layout helpers for Authsome."""

from __future__ import annotations

import os
from pathlib import Path

# TODO: These are all store properties, we have a local file store, move them there


def get_authsome_home(home: Path | None = None) -> Path:
    """Return the root Authsome home directory."""
    if home is not None:
        return home
    return Path(os.environ.get("AUTHSOME_HOME", str(Path.home() / ".authsome")))


def get_client_home(home: Path | None = None) -> Path:
    """Return the client-owned Authsome directory."""
    return get_authsome_home(home) / "client"


def get_server_home(home: Path | None = None) -> Path:
    """Return the server-owned Authsome directory."""
    return get_authsome_home(home) / "server"


def get_client_log_path(home: Path | None = None) -> Path:
    """Return the default client log file path."""
    return get_client_home(home) / "logs" / "authsome.log"


def get_server_log_path(home: Path | None = None) -> Path:
    """Return the default server log file path."""
    return get_server_home(home) / "logs" / "authsome.log"


def get_server_audit_db_path(home: Path | None = None) -> Path:
    """Return the server-owned audit event database path."""
    return get_server_home(home) / "audit" / "events.sqlite3"
