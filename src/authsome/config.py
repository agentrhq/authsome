"""Process-wide configuration for Authsome."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from authsome import __version__


class AuthsomeConfig(BaseSettings):
    """Shared Authsome configuration resolved from environment variables."""

    model_config = SettingsConfigDict(populate_by_name=True)

    version: str = __version__
    home: Path = Field(default=Path.home() / ".authsome", validation_alias="AUTHSOME_HOME")
    base_url: str = Field(default="http://127.0.0.1:7998", validation_alias="AUTHSOME_BASE_URL")

    @property
    def client_home(self) -> Path:
        return self.home / "client"

    @property
    def server_home(self) -> Path:
        return self.home / "server"

    @property
    def client_log_path(self) -> Path:
        return self.client_home / "logs" / "authsome.log"

    @property
    def server_log_path(self) -> Path:
        return self.server_home / "logs" / "authsome.log"

    @property
    def client_config_path(self) -> Path:
        return self.client_home / "config.json"

    @property
    def is_local(self) -> bool:
        # Localhost or unix socket or 127.0.0.1
        return self.base_url.startswith("http://") or self.base_url.startswith("unix://")


def get_authsome_config(home: Path | None = None) -> AuthsomeConfig:
    """Return Authsome config, optionally scoped to an explicit home directory."""
    if home is not None:
        return AuthsomeConfig(home=home)
    return AuthsomeConfig()
