import builtins
import sys
from pathlib import Path

import pytest

from authsome.server.store.database import (
    StoreDatabaseConfig,
    build_migrations,
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
        row = await database.fetch_one("SELECT version FROM store_schema_version")
    finally:
        await database.close()

    assert row == {"version": len(build_migrations("sqlite"))}


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

    assert row == {"count": 1}


def test_postgres_url_uses_postgres_backend(tmp_path: Path) -> None:
    config = resolve_store_database_config(
        home=tmp_path,
        database_url="postgresql://authsome:authsome@localhost:5432/authsome",
    )

    assert config.backend == "postgres"
    assert config.dsn.startswith("postgresql://")
