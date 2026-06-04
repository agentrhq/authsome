"""Concrete local dependency wiring for the daemon server."""

from pathlib import Path
from typing import Any

from key_value.aio.stores.disk import DiskStore

from authsome.auth.models.config import ServerConfig
from authsome.config import get_authsome_config
from authsome.server.account_auth import AccountAuthService
from authsome.server.config import get_server_config
from authsome.server.identity_bootstrap import IdentityBootstrapService
from authsome.server.ownership import OwnershipResolver
from authsome.server.secrets import load_master_secret
from authsome.server.store import ServerStore
from authsome.server.store import create_server_store as _create_server_store
from authsome.server.store.repositories import IdentityRegistry
from authsome.server.ui_sessions import UiSessionStore
from authsome.server.urls import build_server_base_url
from authsome.vault import Vault
from authsome.vault.crypto import AesGcmEncryptionWrapper, DekManager


def get_authsome_home() -> Path:
    """Return the local Authsome home directory."""
    return get_authsome_config().home


def get_server_base_url() -> str:
    """Return the daemon's canonical external base URL."""
    return build_server_base_url()


async def create_store(home: Path | None = None) -> ServerStore:
    """Create the server-owned relational Store."""
    return await _create_server_store(home=home or get_authsome_home())


async def load_server_config(store: ServerStore) -> ServerConfig:
    """Load daemon-owned server config from Store."""
    return await store.server_config.load()


async def create_vault(home: Path) -> Vault:
    """Create the daemon vault from an initialized application store."""
    server_config = get_server_config(home)
    raw_kv = DiskStore(directory=str(server_config.kv_store_dir))
    secret = load_master_secret(home)
    dek = await DekManager().load_or_create(secret, raw_kv)
    encrypted_kv = AesGcmEncryptionWrapper(raw_kv, dek=dek)
    return Vault(encrypted_kv)


def create_account_auth_service(store: ServerStore, ui_sessions: UiSessionStore) -> AccountAuthService:
    return AccountAuthService(
        principals=store.principals,
        vaults=store.vaults,
        bindings=store.principal_vault_bindings,
        sessions=ui_sessions,
    )


def create_ownership_resolver(store: ServerStore) -> OwnershipResolver:
    return OwnershipResolver(
        principals=store.principals,
        vaults=store.vaults,
        claims=store.identity_claims,
        bindings=store.principal_vault_bindings,
    )


def create_identity_bootstrap_service(
    identity_registry: IdentityRegistry,
    ui_sessions: Any,
    *,
    store: ServerStore,
    server_base_url: str | None = None,
) -> IdentityBootstrapService:
    return IdentityBootstrapService(
        registry=identity_registry,
        claims=store.identity_claims,
        ui_sessions=ui_sessions,
        server_base_url=server_base_url or get_server_base_url(),
    )
