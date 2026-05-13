"""Concrete local dependency wiring for the daemon server."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from authsome.auth import AuthService

from authsome.server.urls import build_server_base_url
from authsome.store.local import LocalAppStore
from authsome.vault import Vault


def get_authsome_home() -> Path:
    """Return the local Authsome home directory."""
    return Path(os.environ.get("AUTHSOME_HOME", str(Path.home() / ".authsome")))


def get_server_home(home: Path | None = None) -> Path:
    """Return the daemon-owned state directory."""
    return (home or get_authsome_home()) / "server"


def get_server_base_url() -> str:
    """Return the daemon's canonical external base URL."""
    return build_server_base_url()


async def create_vault(home: Path | None = None) -> Vault:
    """Create the daemon vault without requiring caller identity files."""
    from authsome import audit

    resolved_home = home or get_authsome_home()
    audit.setup(resolved_home / "audit.log")
    app_store = LocalAppStore(resolved_home)
    await app_store.ensure_initialized()

    config = await app_store.get_config()
    crypto_mode = config.encryption.mode if config.encryption else "local_key"
    return Vault(
        app_store=app_store,
        crypto_mode=crypto_mode,
        master_key_path=get_server_home(resolved_home) / "master.key",
    )


async def create_auth_service(home: Path | None = None, identity: str | None = None) -> AuthService:
    """Create an auth service scoped to an identity handle."""
    from authsome.auth import AuthService

    if not identity:
        raise ValueError("create_auth_service requires an explicit identity handle")
    vault = await create_vault(home)
    return AuthService(vault=vault, identity=identity)
