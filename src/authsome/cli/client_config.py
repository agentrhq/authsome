"""Caller-local CLI config helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from authsome import __version__
from authsome.paths import get_client_home

ProxyMode = Literal[
    "connected_allow",
    "connected_deny",
    "configured_allow",
    "configured_deny",
]


class ClientConfig(BaseModel):
    """Caller-local config that should not live in daemon-owned storage.

    The proxy_mode field lives here (not in ServerConfig) because the
    mitmproxy addon runs inside the CLI process per `authsome run`
    invocation. The daemon never acts on the mode itself; only the
    caller-local proxy does. Use `authsome config get/set proxy-mode`
    to read or change the mode without hand-editing the file.
    """

    version: str = __version__
    active_identity: str | None = None
    proxy_ca_installed: bool = False
    proxy_mode: ProxyMode = "connected_allow"


def client_config_path(home: Path) -> Path:
    """Return the caller-local config file path."""
    return get_client_home(home) / "config.json"


def load_client_config(home: Path) -> ClientConfig:
    """Load caller-local config, defaulting when absent or invalid."""
    path = client_config_path(home)
    if not path.exists():
        return ClientConfig()
    try:
        return ClientConfig.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return ClientConfig()


def save_client_config(home: Path, config: ClientConfig) -> None:
    """Persist caller-local config."""
    path = client_config_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(config.model_dump_json(indent=2), encoding="utf-8")
