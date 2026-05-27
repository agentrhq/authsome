from __future__ import annotations

from pathlib import Path

import pytest

from authsome.auth.models.config import ServerConfig
from authsome.server.store import create_server_store


@pytest.mark.asyncio
async def test_server_config_defaults_and_persists_in_store(tmp_path: Path) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        config = await store.server_config.load()
        assert isinstance(config, ServerConfig)

        config.encryption.mode = "local_key"
        await store.server_config.save(config)
        loaded = await store.server_config.load()

        assert loaded.encryption.mode == "local_key"
        assert not (tmp_path / "server" / "config.json").exists()
    finally:
        await store.close()
