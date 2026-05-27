from __future__ import annotations

import os
from pathlib import Path

import pytest

from authsome.server.store import create_server_store
from authsome.server.store.database import build_schema


def test_schema_builder_shares_tables_and_uses_backend_boolean_fragments() -> None:
    sqlite_schema = build_schema("sqlite")
    postgres_schema = build_schema("postgres")

    assert len(sqlite_schema) == len(postgres_schema)
    assert any("is_default INTEGER NOT NULL DEFAULT 0" in statement for statement in sqlite_schema)
    assert any("WHERE is_default = 1" in statement for statement in sqlite_schema)
    assert any("is_default BOOLEAN NOT NULL DEFAULT FALSE" in statement for statement in postgres_schema)
    assert any("WHERE is_default = TRUE" in statement for statement in postgres_schema)

    normalized_sqlite = [
        statement.replace("is_default INTEGER NOT NULL DEFAULT 0", "is_default <bool>").replace(
            "WHERE is_default = 1", "WHERE is_default = <true>"
        )
        for statement in sqlite_schema
    ]
    normalized_postgres = [
        statement.replace("is_default BOOLEAN NOT NULL DEFAULT FALSE", "is_default <bool>").replace(
            "WHERE is_default = TRUE", "WHERE is_default = <true>"
        )
        for statement in postgres_schema
    ]
    assert normalized_sqlite == normalized_postgres


@pytest.mark.asyncio
async def test_create_server_store_defaults_to_sqlite_under_home(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AUTHSOME_DATABASE_URL", raising=False)

    store = await create_server_store(home=tmp_path)
    try:
        assert store.backend == "sqlite"
        assert store.home == tmp_path
        assert await store.is_healthy() is True
        assert (tmp_path / "server" / "authsome.db").exists()
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_create_server_store_accepts_sqlite_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "custom.db"
    monkeypatch.setenv("AUTHSOME_DATABASE_URL", f"sqlite:///{db_path}")

    store = await create_server_store(home=tmp_path)
    try:
        assert store.backend == "sqlite"
        assert await store.is_healthy() is True
        assert db_path.exists()
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_create_server_store_accepts_postgres_url(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    database_url = os.environ.get("AUTHSOME_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("AUTHSOME_TEST_DATABASE_URL is not set")
    monkeypatch.setenv("AUTHSOME_DATABASE_URL", database_url)

    store = await create_server_store(home=tmp_path)
    try:
        assert store.backend == "postgres"
        assert await store.is_healthy() is True
    finally:
        await store.close()
