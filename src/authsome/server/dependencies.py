"""Concrete local dependency wiring for the daemon server."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from authsome.auth import AuthService
    from authsome.store.interfaces import AppStore

from authsome.auth.models.config import ServerConfig
from authsome.identity import current_from_home
from authsome.identity.registry import IdentityRegistry
from authsome.paths import get_authsome_home as _get_authsome_home
from authsome.paths import get_server_home as _get_server_home
from authsome.paths import get_server_log_path as _get_server_log_path
from authsome.server.urls import build_server_base_url
from authsome.store.local import LocalAppStore
from authsome.vault import Vault


def get_authsome_home() -> Path:
    """Return the local Authsome home directory."""
    return _get_authsome_home()


def get_server_home(home: Path | None = None) -> Path:
    """Return the daemon-owned state directory."""
    return _get_server_home(home)


def get_server_config_path(home: Path | None = None) -> Path:
    """Return the daemon-owned config file path."""
    return get_server_home(home) / "config.json"


def get_server_log_path(home: Path | None = None) -> Path:
    """Return the daemon-owned structured log path."""
    return _get_server_log_path(home)


def get_identity_registry_path(home: Path | None = None) -> Path:
    """Return the daemon-owned identity registry file path."""
    return get_server_home(home) / "identity_registry.json"


def get_ui_session_secret_path(home: Path | None = None) -> Path:
    """Return the hosted UI session signing-secret path."""
    return get_server_home(home) / "ui_session_secret.key"


def get_server_base_url() -> str:
    """Return the daemon's canonical external base URL."""
    return build_server_base_url()


def get_deployment_mode() -> str:
    """Return the daemon deployment mode."""
    mode = os.environ.get("AUTHSOME_DEPLOYMENT_MODE", "local").strip().lower()
    return "hosted" if mode == "hosted" else "local"


def load_ui_session_signing_secret(home: Path | None = None) -> str:
    """Load or create the hosted UI session signing secret."""
    path = get_ui_session_secret_path(home)
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        path.parent.mkdir(parents=True, exist_ok=True)
        secret = secrets.token_hex(32)
        path.write_text(secret, encoding="utf-8")
        os.chmod(path, 0o600)
        return secret


async def get_local_ui_identity(home: Path | None = None) -> str:
    """Resolve the local active identity handle for the server-rendered UI."""
    identity = await current_from_home(home or get_authsome_home())
    return identity.handle


def load_server_config(home: Path | None = None) -> ServerConfig:
    """Load daemon-owned server config, defaulting when absent or invalid."""
    path = get_server_config_path(home)
    try:
        return ServerConfig.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        config = ServerConfig()
        save_server_config(config, home)
        return config


def save_server_config(config: ServerConfig, home: Path | None = None) -> None:
    """Persist daemon-owned server config."""
    path = get_server_config_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(config.model_dump_json(indent=2), encoding="utf-8")


async def create_app_store(home: Path | None = None) -> AppStore:
    """Create the daemon application store."""
    resolved_home = home or get_authsome_home()
    load_server_config(resolved_home)
    app_store = LocalAppStore(resolved_home)
    await app_store.ensure_initialized()
    return app_store


async def list_registered_identity_handles(home: Path | None = None) -> list[str]:
    """Return identity handles registered with this daemon."""
    registry = IdentityRegistry(get_identity_registry_path(home))
    return await registry.list_handles()


async def create_vault(app_store: AppStore) -> Vault:
    """Create the daemon vault from an initialized application store."""
    resolved_home = app_store.home
    return Vault(
        app_store=app_store,
        crypto_mode=get_deployment_mode(),
        master_key_path=get_server_home(resolved_home) / "master.key",
    )


async def create_auth_service(home: Path | None = None, identity: str | None = None) -> AuthService:
    """Create an auth service scoped to an identity handle."""
    from authsome.auth import AuthService

    if not identity:
        raise ValueError("create_auth_service requires an explicit identity handle")
    store = await create_app_store(home)
    vault = await create_vault(store)
    return AuthService(vault=vault, identity=identity, deployment_mode=get_deployment_mode())
