import builtins
import sys
import types
from pathlib import Path

import pytest
from fastapi import FastAPI

from authsome.auth.sessions import MemoryAuthSessionStore
from authsome.server.app import lifespan
from authsome.server.auth_sessions import RedisAuthSessionStore
from authsome.server.config import get_server_config
from authsome.server.dependencies import create_runtime_state, create_vault
from authsome.server.replay_cache import MemoryReplayCache, RedisReplayCache
from authsome.server.ui_sessions import MemoryPendingClaimStore, RedisPendingClaimStore


class FakeRedisClient:
    last_created = None

    def __init__(self) -> None:
        self.ping_called = False
        self.aclose_called = False

    @classmethod
    def from_url(cls, url: str, decode_responses: bool = False):
        client = cls()
        cls.last_created = client
        client.url = url
        client.decode_responses = decode_responses
        return client

    async def ping(self) -> None:
        self.ping_called = True

    async def aclose(self) -> None:
        self.aclose_called = True


class FailingPingRedisClient(FakeRedisClient):
    async def ping(self) -> None:
        self.ping_called = True
        raise ConnectionError("ping failed")


class FakeAuditLog:
    def __init__(self) -> None:
        self.shutdown_called = False

    def shutdown(self) -> None:
        self.shutdown_called = True

    async def async_shutdown(self) -> None:
        self.shutdown()


class FakeStore:
    def __init__(self, home: Path, audit_log: FakeAuditLog) -> None:
        self.home = home
        self.close_called = False
        self.provider_definitions = object()
        self.identity_registry = object()
        self.audit_events = types.SimpleNamespace(configure_exporter=lambda: audit_log)

    async def close(self) -> None:
        self.close_called = True


class FakeRuntimeState:
    def __init__(self) -> None:
        self.close_called = False
        self.auth_sessions = object()
        self.replay_cache = object()
        self.pending_claims = object()

    async def close(self) -> None:
        self.close_called = True


def _patch_import(monkeypatch: pytest.MonkeyPatch, module_name: str, module: types.ModuleType | None) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, globals=None, locals=None, fromlist=(), level=0):
        if name == module_name or name.startswith(f"{module_name}."):
            if module is None:
                raise ImportError(module_name)
            return sys.modules.get(name, module)
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)


@pytest.mark.asyncio
async def test_runtime_state_defaults_to_memory_without_redis(monkeypatch) -> None:
    monkeypatch.delenv("AUTHSOME_REDIS_URL", raising=False)
    get_server_config.cache_clear()

    state = await create_runtime_state()
    try:
        assert isinstance(state.auth_sessions, MemoryAuthSessionStore)
        assert isinstance(state.replay_cache, MemoryReplayCache)
        assert isinstance(state.pending_claims, MemoryPendingClaimStore)
        assert state.redis_client is None
    finally:
        await state.close()


@pytest.mark.asyncio
async def test_runtime_state_raises_when_redis_package_missing(monkeypatch) -> None:
    monkeypatch.setenv("AUTHSOME_REDIS_URL", "redis://localhost:6379/0")
    get_server_config.cache_clear()
    _patch_import(monkeypatch, "redis", None)

    with pytest.raises(RuntimeError, match="Redis state requires installing authsome\\[redis\\]"):
        await create_runtime_state()


@pytest.mark.asyncio
async def test_runtime_state_uses_redis_stores_and_pings_client(monkeypatch) -> None:
    monkeypatch.setenv("AUTHSOME_REDIS_URL", "redis://localhost:6379/0")
    get_server_config.cache_clear()
    redis_asyncio = types.ModuleType("redis.asyncio")
    redis_asyncio.Redis = FakeRedisClient
    monkeypatch.setitem(sys.modules, "redis.asyncio", redis_asyncio)
    monkeypatch.setitem(sys.modules, "redis", types.ModuleType("redis"))
    _patch_import(monkeypatch, "redis", sys.modules["redis"])
    sys.modules["redis"].asyncio = redis_asyncio

    state = await create_runtime_state()
    try:
        assert isinstance(state.auth_sessions, RedisAuthSessionStore)
        assert isinstance(state.replay_cache, RedisReplayCache)
        assert isinstance(state.pending_claims, RedisPendingClaimStore)
        assert state.redis_client is not None
        assert state.redis_client.url == "redis://localhost:6379/0"
        assert state.redis_client.decode_responses is True
        assert state.redis_client.ping_called is True
    finally:
        await state.close()

    assert state.redis_client.aclose_called is True


@pytest.mark.asyncio
async def test_runtime_state_closes_redis_client_when_ping_fails(monkeypatch) -> None:
    monkeypatch.setenv("AUTHSOME_REDIS_URL", "redis://localhost:6379/0")
    get_server_config.cache_clear()
    redis_asyncio = types.ModuleType("redis.asyncio")
    redis_asyncio.Redis = FailingPingRedisClient
    monkeypatch.setitem(sys.modules, "redis.asyncio", redis_asyncio)
    monkeypatch.setitem(sys.modules, "redis", types.ModuleType("redis"))
    _patch_import(monkeypatch, "redis", sys.modules["redis"])
    sys.modules["redis"].asyncio = redis_asyncio

    with pytest.raises(ConnectionError, match="ping failed"):
        await create_runtime_state()

    assert FailingPingRedisClient.last_created is not None
    assert FailingPingRedisClient.last_created.aclose_called is True


@pytest.mark.asyncio
async def test_lifespan_cleans_up_partial_startup_on_failure(monkeypatch, tmp_path: Path) -> None:
    from authsome.server import app as app_module

    audit_log = FakeAuditLog()
    store = FakeStore(tmp_path, audit_log)
    runtime_state = FakeRuntimeState()

    async def create_store(home=None):
        return store

    async def load_server_config(_store):
        return object()

    async def create_vault(_home):
        return object()

    async def create_runtime_state_stub():
        return runtime_state

    def raise_startup_error(*args, **kwargs):
        raise RuntimeError("startup boom")

    monkeypatch.setattr(app_module, "create_store", create_store)
    monkeypatch.setattr(app_module, "load_server_config", load_server_config)
    monkeypatch.setattr(app_module, "create_vault", create_vault)
    monkeypatch.setattr(app_module, "create_runtime_state", create_runtime_state_stub)
    monkeypatch.setattr(app_module, "create_account_auth_service", raise_startup_error)
    monkeypatch.setattr(app_module, "load_ui_session_signing_secret", lambda home: "secret")
    monkeypatch.setattr(app_module, "init_posthog", lambda: None)
    monkeypatch.setattr(app_module, "shutdown_posthog", lambda: None)

    with pytest.raises(RuntimeError, match="startup boom"):
        async with lifespan(FastAPI()):
            pass

    assert store.close_called is True
    assert audit_log.shutdown_called is True
    assert runtime_state.close_called is True


@pytest.mark.asyncio
async def test_create_vault_uses_disk_store_without_redis(monkeypatch, tmp_path: Path) -> None:
    from authsome.server import dependencies

    class FakeDiskStore:
        def __init__(self, directory: str) -> None:
            self.directory = directory

    class FakeDekManager:
        async def load_or_create(self, secret, raw_kv):
            return object()

    monkeypatch.delenv("AUTHSOME_REDIS_URL", raising=False)
    monkeypatch.setattr(dependencies, "DiskStore", FakeDiskStore)
    monkeypatch.setattr(dependencies, "DekManager", FakeDekManager)
    monkeypatch.setattr(dependencies, "load_master_secret", lambda home: "secret")
    monkeypatch.setattr(dependencies, "AesGcmEncryptionWrapper", lambda raw_kv, dek: raw_kv)
    monkeypatch.setattr(dependencies, "Vault", lambda encrypted_kv: encrypted_kv)

    vault = await create_vault(tmp_path)

    assert isinstance(vault, FakeDiskStore)
    assert vault.directory == str(tmp_path / "server" / "kv_store")


@pytest.mark.asyncio
async def test_create_vault_uses_redis_store_when_redis_configured(monkeypatch, tmp_path: Path) -> None:
    from authsome.server import dependencies

    class FakeRedisStore:
        def __init__(self, url: str) -> None:
            self.url = url
            self.get_calls: list[tuple[str, str | None]] = []

        async def get(self, key: str, *, collection: str | None = None):
            self.get_calls.append((key, collection))

    class FakeDekManager:
        async def load_or_create(self, secret, raw_kv):
            return object()

    redis_store_module = types.ModuleType("key_value.aio.stores.redis")
    redis_store_module.RedisStore = FakeRedisStore

    monkeypatch.setenv("AUTHSOME_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(dependencies, "DekManager", FakeDekManager)
    monkeypatch.setattr(dependencies, "load_master_secret", lambda home: "secret")
    monkeypatch.setattr(dependencies, "AesGcmEncryptionWrapper", lambda raw_kv, dek: raw_kv)
    monkeypatch.setattr(dependencies, "Vault", lambda encrypted_kv: encrypted_kv)
    _patch_import(monkeypatch, "key_value.aio.stores.redis", redis_store_module)

    vault = await create_vault(tmp_path)

    assert isinstance(vault, FakeRedisStore)
    assert vault.url == "redis://localhost:6379/0"
    assert vault.get_calls == [("__integrity_probe__", "__vault_meta__")]


@pytest.mark.asyncio
async def test_create_vault_raises_clear_error_when_redis_probe_fails(monkeypatch, tmp_path: Path) -> None:
    from authsome.server import dependencies

    class FailingRedisStore:
        def __init__(self, url: str) -> None:
            self.url = url

        async def get(self, key: str, *, collection: str | None = None):
            raise ConnectionError("redis down")

    redis_store_module = types.ModuleType("key_value.aio.stores.redis")
    redis_store_module.RedisStore = FailingRedisStore

    monkeypatch.setenv("AUTHSOME_REDIS_URL", "redis://localhost:6379/0")
    get_server_config.cache_clear()
    monkeypatch.setattr(dependencies, "AesGcmEncryptionWrapper", lambda raw_kv, dek: raw_kv)
    monkeypatch.setattr(dependencies, "Vault", lambda encrypted_kv: encrypted_kv)
    _patch_import(monkeypatch, "key_value.aio.stores.redis", redis_store_module)

    with pytest.raises(RuntimeError, match="Redis vault storage is unavailable"):
        await create_vault(tmp_path)
