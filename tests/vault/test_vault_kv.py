from __future__ import annotations

from pathlib import Path

import pytest
from key_value.aio.stores.disk import DiskStore

from authsome.vault import Vault


@pytest.mark.asyncio
async def test_vault_accepts_py_key_value_adapter_directly(tmp_path: Path) -> None:
    kv = DiskStore(directory=str(tmp_path / "kv"))
    vault = Vault(kv=kv, master_key_path=tmp_path / "master.key", crypto_mode="local_key")
    try:
        await vault.put("github", "secret", collection="vault:test")

        assert await vault.get("github", collection="vault:test") == "secret"
        assert await vault.list(collection="vault:test") == ["github"]
    finally:
        await vault.close()
