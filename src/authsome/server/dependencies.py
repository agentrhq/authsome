"""Concrete local dependency wiring for the daemon server."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from authsome.server.credential_service import AuthService

from key_value.aio.stores.disk import DiskStore

from authsome.auth.models.config import ServerConfig
from authsome.identity import current_from_home
from authsome.paths import get_authsome_home as _get_authsome_home
from authsome.paths import get_server_home as _get_server_home
from authsome.paths import get_server_log_path as _get_server_log_path
from authsome.server.credential_repository import CredentialRepository
from authsome.server.hosted_auth import HostedAccountService
from authsome.server.identity_bootstrap import (
    HostedIdentityBootstrapService,
    IdentityBootstrapService,
    LocalIdentityBootstrapService,
)
from authsome.server.ownership import HostedOwnershipResolver, LocalOwnershipResolver, OwnershipResolver
from authsome.server.provider_repository import ProviderRepository
from authsome.server.secrets import load_master_secret, load_ui_session_signing_secret
from authsome.server.store import ServerStore
from authsome.server.store import create_server_store as _create_server_store
from authsome.server.store.repositories import IdentityRegistry
from authsome.server.urls import build_server_base_url
from authsome.vault import Vault
from authsome.vault.crypto import AesGcmEncryptionWrapper, DekManager


def get_authsome_home() -> Path:
    """Return the local Authsome home directory."""
    return _get_authsome_home()


def get_server_home(home: Path | None = None) -> Path:
    """Return the daemon-owned state directory."""
    return _get_server_home(home)


def get_server_log_path(home: Path | None = None) -> Path:
    """Return the daemon-owned structured log path."""
    return _get_server_log_path(home)


def get_server_base_url() -> str:
    """Return the daemon's canonical external base URL."""
    return build_server_base_url()


def get_deployment_mode() -> str:
    """Return the daemon deployment mode."""
    mode = os.environ.get("AUTHSOME_DEPLOYMENT_MODE", "local").strip().lower()
    return "hosted" if mode == "hosted" else "local"


async def get_local_ui_identity(home: Path | None = None) -> str:
    """Resolve the local active identity handle for the server-rendered UI."""
    identity = await current_from_home(home or get_authsome_home())
    return identity.handle


async def create_store(home: Path | None = None) -> ServerStore:
    """Create the server-owned relational Store."""
    return await _create_server_store(home=home or get_authsome_home())


async def load_server_config(store: ServerStore) -> ServerConfig:
    """Load daemon-owned server config from Store."""
    return await store.server_config.load()


async def save_server_config(store: ServerStore, config: ServerConfig) -> None:
    """Persist daemon-owned server config to Store."""
    await store.server_config.save(config)


async def list_registered_identity_handles(home: Path | None = None) -> list[str]:
    """Return identity handles registered with this daemon."""
    store = await create_store(home)
    try:
        return await store.identity_registry.list_handles()
    finally:
        await store.close()


async def create_vault(home: Path) -> Vault:
    """Create the daemon vault from an initialized application store."""
    server_home = get_server_home(home)
    raw_kv = DiskStore(directory=str(server_home / "kv_store"))
    secret = load_master_secret(home)
    dek = await DekManager().load_or_create(secret, raw_kv)
    encrypted_kv = AesGcmEncryptionWrapper(raw_kv, dek=dek)
    return Vault(encrypted_kv)


def create_credential_repository(
    *,
    vault: Vault,
    identity: str | None,
    principal_id: str | None,
    vault_id: str,
) -> CredentialRepository:
    return CredentialRepository(
        vault,
        identity=identity,
        principal_id=principal_id,
        vault_id=vault_id,
    )


async def create_auth_service(
    home: Path | None = None, identity: str | None = None, vault_id: str | None = None
) -> AuthService:
    """Create an auth service scoped to an identity handle and an explicit vault_id."""
    from authsome.server.credential_service import AuthService

    if not identity:
        raise ValueError("create_auth_service requires an explicit identity handle")
    if not vault_id:
        raise ValueError("create_auth_service requires an explicit vault_id")
    store = await create_store(home)
    vault = await create_vault(store.home)
    return AuthService(
        credentials=create_credential_repository(
            vault=vault,
            identity=identity,
            principal_id=None,
            vault_id=vault_id,
        ),
        providers=ProviderRepository(store.provider_definitions),
        identity=identity,
        vault_id=vault_id,
        deployment_mode=get_deployment_mode(),
    )


def create_hosted_account_service(store: ServerStore) -> HostedAccountService:
    return HostedAccountService(
        principals=store.principals,
        vaults=store.vaults,
        bindings=store.principal_vault_bindings,
        jwt_secret=load_ui_session_signing_secret(store.home),
    )


def create_ownership_resolver(store: ServerStore) -> OwnershipResolver:
    if get_deployment_mode() == "hosted":
        return HostedOwnershipResolver(
            principals=store.principals,
            vaults=store.vaults,
            claims=store.identity_claims,
            bindings=store.principal_vault_bindings,
        )
    return LocalOwnershipResolver(
        principals=store.principals,
        vaults=store.vaults,
        bindings=store.principal_vault_bindings,
    )


def create_identity_bootstrap_service(
    identity_registry: IdentityRegistry,
    ui_sessions: Any,
    *,
    store: ServerStore,
    server_base_url: str | None = None,
) -> IdentityBootstrapService:
    if get_deployment_mode() == "hosted":
        return HostedIdentityBootstrapService(
            registry=identity_registry,
            claims=store.identity_claims,
            ui_sessions=ui_sessions,
            server_base_url=server_base_url or get_server_base_url(),
        )
    return LocalIdentityBootstrapService(registry=identity_registry)
