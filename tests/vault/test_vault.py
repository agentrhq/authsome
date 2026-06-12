import json
from collections.abc import Mapping, Sequence
from typing import Any, SupportsFloat

import pytest

from authsome.vault import Vault


class EnumerableKv:
    def __init__(self) -> None:
        self.data: dict[str, dict[str, dict[str, Any]]] = {}

    async def get(self, key: str, *, collection: str | None = None) -> dict[str, Any] | None:
        return self.data.get(collection or "default_collection", {}).get(key)

    async def put(
        self,
        key: str,
        value: Mapping[str, Any],
        *,
        collection: str | None = None,
        ttl: SupportsFloat | None = None,
    ) -> None:
        _ = ttl
        self.data.setdefault(collection or "default_collection", {})[key] = dict(value)

    async def delete(self, key: str, *, collection: str | None = None) -> bool:
        values = self.data.setdefault(collection or "default_collection", {})
        existed = key in values
        values.pop(key, None)
        return existed

    async def get_many(self, keys: Sequence[str], *, collection: str | None = None) -> list[dict[str, Any] | None]:
        return [await self.get(key, collection=collection) for key in keys]

    async def put_many(
        self,
        keys: Sequence[str],
        values: Sequence[Mapping[str, Any]],
        *,
        collection: str | None = None,
        ttl: SupportsFloat | None = None,
    ) -> None:
        for key, value in zip(keys, values, strict=True):
            await self.put(key, value, collection=collection, ttl=ttl)

    async def delete_many(self, keys: Sequence[str], *, collection: str | None = None) -> int:
        deleted = 0
        for key in keys:
            if await self.delete(key, collection=collection):
                deleted += 1
        return deleted

    async def ttl(self, key: str, *, collection: str | None = None) -> tuple[dict[str, Any] | None, float | None]:
        return await self.get(key, collection=collection), None

    async def ttl_many(
        self,
        keys: Sequence[str],
        *,
        collection: str | None = None,
    ) -> list[tuple[dict[str, Any] | None, float | None]]:
        return [await self.ttl(key, collection=collection) for key in keys]

    async def keys(self, collection: str | None = None, *, limit: int | None = None) -> list[str]:
        keys = sorted(self.data.get(collection or "default_collection", {}))
        return keys[:limit] if limit is not None else keys


@pytest.mark.asyncio
async def test_vault_lists_from_enumerable_backend_instead_of_manual_index() -> None:
    kv = EnumerableKv()
    vault = Vault(kv)

    await vault.put("beta", "2", collection="vault:vault_1")
    await vault.put("alpha", "1", collection="vault:vault_1")
    kv.data["vault:vault_1"]["__index__"] = {"data": json.dumps(["stale"])}

    assert await vault.list(collection="vault:vault_1") == ["alpha", "beta"]
    assert await vault.list("alp", collection="vault:vault_1") == ["alpha"]

    await vault.delete("alpha", collection="vault:vault_1")

    assert await vault.list(collection="vault:vault_1") == ["beta"]
    assert kv.data["vault:vault_1"]["__index__"] == {"data": json.dumps(["stale"])}
