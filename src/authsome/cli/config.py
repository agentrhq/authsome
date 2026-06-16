"""Caller-local CLI config helpers."""

from functools import lru_cache
from pathlib import Path

from authsome.config import AuthsomeConfig, get_authsome_config
from authsome.proxy.config import ProxyMode


class ClientConfig(AuthsomeConfig):
    """Caller-local config that should not live in daemon-owned storage.

    The proxy_mode field lives here (not in ServerConfig) because the
    mitmproxy addon runs inside the CLI process per `authsome run`
    invocation. The daemon never acts on the mode itself; only the
    caller-local proxy does. Users can change the mode by editing this
    file directly — there is no CLI command for it today (YAGNI).
    """

    active_identity: str | None = None
    daemon_base_url: str | None = None
    proxy_ca_installed: bool = False
    proxy_mode: ProxyMode = "connected_allow"

    @property
    def identities_dir(self) -> Path:
        return self.client_home / "identities"

    @classmethod
    def load(cls, home: Path | None = None) -> "ClientConfig":
        path = get_authsome_config(home).client_config_path

        if not path.exists():
            return cls(home=home) if home is not None else cls()
        try:
            config = cls.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            return cls(home=home) if home is not None else cls()
        if home is not None:
            return config.model_copy(update={"home": home})
        return config

    def save(self, home: Path | None = None) -> None:
        path = get_authsome_config(home).client_config_path
        path.parent.mkdir(parents=True, exist_ok=True)
        # Exclude inherited settings fields — only persist client-local state.
        path.write_text(self.model_dump_json(indent=2, exclude={"home", "base_url", "version"}), encoding="utf-8")


@lru_cache
def get_client_config(home: Path | None = None) -> ClientConfig:
    return ClientConfig.load(home)
