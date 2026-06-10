"""Daemon-owned runtime configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field

from authsome.config import AuthsomeConfig


class ServerConfig(AuthsomeConfig):
    """Daemon runtime settings resolved from ``AUTHSOME_*`` environment variables."""

    # Network
    host: str = "127.0.0.1"
    port: int = 7998

    # Store
    database_url: str | None = Field(default=None, validation_alias="DATABASE_URL")
    redis_url: str | None = None
    postgres_pool_min_size: int = Field(default=1, ge=1)
    postgres_pool_max_size: int = Field(default=10, ge=1)

    # Lifetimes, in seconds
    ui_bootstrap_ttl_seconds: int = 300
    ui_session_ttl_seconds: int = 3600
    token_near_expiry_seconds: int = 300

    # Account policy
    min_password_length: int = Field(default=8)

    # Analytics
    posthog_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("AUTHSOME_POSTHOG_API_KEY", "POSTHOG_API_KEY"),
    )
    posthog_host: str = "https://us.i.posthog.com"
    do_not_track: bool = Field(
        default=False,
        validation_alias=AliasChoices("AUTHSOME_DO_NOT_TRACK", "DO_NOT_TRACK"),
    )

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
    def analytics_enabled(self) -> bool:
        """True when daemon telemetry has not been opted out."""
        return bool(self.posthog_api_key) and not self.do_not_track

    @property
    def database(self) -> str:
        if self.database_url is not None:
            return self.database_url
        return str(self.server_home / "authsome.db")


@lru_cache
def get_server_config(home: Path | None = None) -> ServerConfig:
    """Return daemon config, optionally scoped to an explicit home directory."""
    if home is not None:
        return ServerConfig(home=home)
    return ServerConfig()
