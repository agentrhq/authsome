"""Concrete local dependency wiring for the daemon server."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from key_value.aio.stores.disk import DiskStore

from authsome.auth.models.config import ServerConfig
from authsome.auth.sessions import MemoryAuthSessionStore
from authsome.config import get_authsome_config
from authsome.server.account_auth import AccountAuthService
from authsome.server.auth_sessions import RedisAuthSessionStore
from authsome.server.config import get_server_config
from authsome.server.identity_bootstrap import IdentityBootstrapService
from authsome.server.ownership import OwnershipResolver
from authsome.server.replay_cache import MemoryReplayCache, RedisReplayCache
from authsome.server.secrets import load_master_secret
from authsome.server.store import ServerStore
from authsome.server.store import create_server_store as _create_server_store
from authsome.server.store.repositories import IdentityRegistry
from authsome.server.ui_sessions import MemoryPendingClaimStore, RedisPendingClaimStore, UiSessionStore
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
    if server_config.redis_url:
        try:
            redis_store_module = __import__("key_value.aio.stores.redis", fromlist=["RedisStore"])
        except ImportError as exc:
            raise RuntimeError("Redis vault storage requires installing authsome[redis]") from exc

        RedisStore = cast(Any, redis_store_module).RedisStore
        raw_kv = RedisStore(url=server_config.redis_url)
        try:
            await raw_kv.get("__integrity_probe__", collection="__vault_meta__")
        except Exception as exc:
            raise RuntimeError("Redis vault storage is unavailable") from exc
    else:
        raw_kv = DiskStore(directory=str(server_config.kv_store_dir))
    secret = load_master_secret(home)
    dek = await DekManager().load_or_create(secret, raw_kv)
    encrypted_kv = AesGcmEncryptionWrapper(raw_kv, dek=dek)
    return Vault(encrypted_kv)


@dataclass
class RuntimeState:
    auth_sessions: MemoryAuthSessionStore | RedisAuthSessionStore
    replay_cache: MemoryReplayCache | RedisReplayCache
    pending_claims: MemoryPendingClaimStore | RedisPendingClaimStore
    redis_client: Any | None = None

    async def close(self) -> None:
        if self.redis_client is not None:
            await self.redis_client.aclose()


async def create_runtime_state() -> RuntimeState:
    config = get_server_config()
    if not config.redis_url:
        return RuntimeState(
            auth_sessions=MemoryAuthSessionStore(),
            replay_cache=MemoryReplayCache(),
            pending_claims=MemoryPendingClaimStore(),
        )
    try:
        redis_module = __import__("redis.asyncio", fromlist=["Redis"])
    except ImportError as exc:
        raise RuntimeError("Redis state requires installing authsome[redis]") from exc

    Redis = cast(Any, redis_module).Redis
    client = Redis.from_url(config.redis_url, decode_responses=True)
    await client.ping()
    return RuntimeState(
        auth_sessions=RedisAuthSessionStore(client),
        replay_cache=RedisReplayCache(client),
        pending_claims=RedisPendingClaimStore(client),
        redis_client=client,
    )


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
