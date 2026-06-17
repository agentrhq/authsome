import builtins
import sys
from pathlib import Path

import pytest

from authsome.server.store.database import (
    StoreDatabase,
    StoreDatabaseConfig,
    build_migrations,
    initialize_schema,
    open_store_database,
    resolve_store_database_config,
)


@pytest.mark.asyncio
async def test_open_store_database_postgres_without_driver_raises_runtime_error(monkeypatch, tmp_path) -> None:
    postgres_config = StoreDatabaseConfig(backend="postgres", dsn="postgres://localhost:5432/test", home=tmp_path)
    original_import = builtins.__import__
    removed_asyncpg = sys.modules.pop("asyncpg", None)

    def fake_import(name: str, *args, **kwargs):
        if name == "asyncpg":
            raise ImportError("No module named 'asyncpg'")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    try:
        with pytest.raises(RuntimeError, match=r"Postgres Store requires installing authsome\[postgres\]"):
            await open_store_database(postgres_config)
    finally:
        if removed_asyncpg is not None:
            sys.modules["asyncpg"] = removed_asyncpg


@pytest.mark.asyncio
async def test_sqlite_migrations_create_schema_version(tmp_path: Path) -> None:
    config = resolve_store_database_config(home=tmp_path)
    database = await open_store_database(config)

    try:
        row = await database.fetch_one("SELECT MAX(version) AS version FROM store_schema_version")
    finally:
        await database.close()

    assert row == {"version": max(migration.version for migration in build_migrations("sqlite"))}


@pytest.mark.asyncio
async def test_sqlite_migrations_are_idempotent(tmp_path: Path) -> None:
    config = resolve_store_database_config(home=tmp_path)
    first = await open_store_database(config)
    await first.close()

    second = await open_store_database(config)
    try:
        row = await second.fetch_one("SELECT COUNT(*) AS count FROM store_schema_version")
    finally:
        await second.close()

    assert row == {"count": len(build_migrations("sqlite"))}


def test_postgres_url_uses_postgres_backend(tmp_path: Path) -> None:
    config = resolve_store_database_config(
        home=tmp_path,
        database_url="postgresql://authsome:authsome@localhost:5432/authsome",
    )

    assert config.backend == "postgres"
    assert config.dsn.startswith("postgresql://")


class _FakeTransaction:
    def __init__(self, connection) -> None:
        self._connection = connection

    async def __aenter__(self):
        self._connection.transaction_enters += 1
        return self._connection

    async def __aexit__(self, exc_type, exc, tb):
        self._connection.transaction_exits += 1
        return False


class _FakeConnection:
    def __init__(self) -> None:
        self.execute_calls: list[tuple[str, tuple[object, ...]]] = []
        self.fetchrow_calls: list[tuple[str, tuple[object, ...]]] = []
        self.fetch_calls: list[tuple[str, tuple[object, ...]]] = []
        self.transaction_enters = 0
        self.transaction_exits = 0

    def transaction(self) -> _FakeTransaction:
        return _FakeTransaction(self)

    async def execute(self, sql: str, *params: object):
        self.execute_calls.append((sql, params))

    async def fetchrow(self, sql: str, *params: object):
        self.fetchrow_calls.append((sql, params))

    async def fetch(self, sql: str, *params: object):
        self.fetch_calls.append((sql, params))
        return []

    async def close(self) -> None:
        return None


class _FakeAcquire:
    def __init__(self, pool, connection) -> None:
        self._pool = pool
        self._connection = connection

    async def __aenter__(self):
        self._pool.acquire_count += 1
        return self._connection

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakePool:
    def __init__(self, connection) -> None:
        self._connection = connection
        self.acquire_count = 0
        self.close_count = 0

    def acquire(self) -> _FakeAcquire:
        return _FakeAcquire(self, self._connection)

    async def close(self) -> None:
        self.close_count += 1


@pytest.mark.asyncio
async def test_postgres_transaction_uses_single_pooled_connection(tmp_path: Path) -> None:
    config = StoreDatabaseConfig(backend="postgres", dsn="postgresql://localhost:5432/authsome", home=tmp_path)
    connection = _FakeConnection()
    pool = _FakePool(connection)
    db = StoreDatabase(config=config, pool=pool)
    try:
        async with db.transaction():
            await db.execute("INSERT INTO audit_events (event_id) VALUES (?)", ["evt_1"])
    finally:
        await db.close()

    assert pool.acquire_count == 1
    assert connection.execute_calls == [("INSERT INTO audit_events (event_id) VALUES ($1)", ("evt_1",))]


@pytest.mark.asyncio
async def test_postgres_migrations_take_advisory_lock(tmp_path: Path) -> None:
    config = StoreDatabaseConfig(backend="postgres", dsn="postgresql://localhost:5432/authsome", home=tmp_path)
    connection = _FakeConnection()
    db = StoreDatabase(config=config, connection=connection)
    try:
        await initialize_schema(db)
    finally:
        await db.close()

    assert connection.transaction_enters == 1
    assert connection.transaction_exits == 1
    assert connection.execute_calls[0][0] == "SELECT pg_advisory_xact_lock($1)"
    assert isinstance(connection.execute_calls[0][1][0], int)
