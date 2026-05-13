"""Client-side identity selection config."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class ClientConfig(BaseModel):
    """Caller-local config that should not live in daemon-owned storage."""

    active_identity: str | None = None


def client_config_path(home: Path) -> Path:
    """Return the caller-local config file path."""
    return home / "config.json"


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
    home.mkdir(parents=True, exist_ok=True)
    client_config_path(home).write_text(config.model_dump_json(indent=2), encoding="utf-8")
