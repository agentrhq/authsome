"""Daemon-owned runtime configuration."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from authsome.config import get_authsome_config


class ServerConfig(BaseSettings):
    """Daemon runtime settings resolved from ``AUTHSOME_*`` environment variables."""

    model_config = SettingsConfigDict(env_prefix="AUTHSOME_", extra="ignore")

    home: Path = Field(default_factory=lambda: get_authsome_config().home)

    # Network
    host: str = "127.0.0.1"
    port: int = 7998
    server_base_url: str = ""

    # Store
    database_url: str = ""

    # Lifetimes, in seconds
    ui_bootstrap_ttl_seconds: int = 300
    ui_session_ttl_seconds: int = 3600
    token_near_expiry_seconds: int = 300

    # Account policy
    min_password_length: int = 8

    # Analytics
    analytics: bool = True
    posthog_api_key: str = "YOUR_API_KEY_HERE"
    posthog_host: str = "https://us.i.posthog.com"
    do_not_track: bool = Field(default=False, validation_alias=AliasChoices("DO_NOT_TRACK"))
    posthog_disabled: bool = Field(default=False, validation_alias=AliasChoices("POSTHOG_DISABLED"))

    @property
    def server_home(self) -> Path:
        return self.home / "server"

    @property
    def daemon_dir(self) -> Path:
        return self.server_home / "daemon"

    @property
    def daemon_pid_file(self) -> Path:
        return self.daemon_dir / "daemon.pid"

    @property
    def daemon_log_file(self) -> Path:
        return self.daemon_dir / "daemon.log"

    @property
    def daemon_state_file(self) -> Path:
        return self.daemon_dir / "daemon.json"

    @property
    def kv_store_dir(self) -> Path:
        return self.server_home / "kv_store"

    @property
    def sqlite_database_path(self) -> Path:
        return self.server_home / "authsome.db"

    @property
    def resolved_base_url(self) -> str:
        """Canonical external base URL, derived from host/port when unset."""
        return (self.server_base_url or f"http://{self.host}:{self.port}").rstrip("/")

    @property
    def analytics_enabled(self) -> bool:
        """True only when analytics is on and no opt-out flag is set."""
        return self.analytics and not self.do_not_track and not self.posthog_disabled


@lru_cache
def get_server_config(home: Path | None = None) -> ServerConfig:
    """Return daemon config, optionally scoped to an explicit home directory."""
    if home is not None:
        return ServerConfig(home=home)
    return ServerConfig()
