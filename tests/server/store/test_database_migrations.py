import builtins
import sys

import pytest

from authsome.server.store.database import StoreDatabaseConfig, open_store_database


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
