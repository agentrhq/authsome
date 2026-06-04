"""Vault — encrypted key-value layer over AsyncKeyValue."""

import builtins
import json

from key_value.aio.protocols.key_value import AsyncKeyValue


class Vault:
    """Thin domain wrapper over an already-encrypted AsyncKeyValue store.

    Encryption is handled by AesGcmEncryptionWrapper at construction time.
    This class owns the index records used for prefix listing.
    """

    def __init__(self, kv: AsyncKeyValue) -> None:
        self._kv = kv

    @property
    def crypto_source(self) -> str:
        return "aes-256-gcm"

    @property
    def crypto_source_description(self) -> str:
        return "AES-256-GCM with Argon2id-derived DEK"

    @property
    def crypto_mode(self) -> str:
        return "aes-256-gcm"

    # ── Index helpers ─────────────────────────────────────────────────────

    async def _get_index(self, collection: str) -> builtins.list[str]:
        val = await self._kv.get("__index__", collection=collection)
        if not val:
            return []
        return json.loads(val["data"])

    async def _save_index(self, collection: str, keys: builtins.list[str]) -> None:
        await self._kv.put("__index__", {"data": json.dumps(sorted(keys))}, collection=collection)

    # ── Encrypted KV interface ────────────────────────────────────────────

    async def get(self, key: str, *, collection: str) -> str | None:
        """Retrieve and decrypt a value. Returns None if key not found."""
        val = await self._kv.get(key, collection=collection)
        if val is None:
            return None
        return val["data"]

    async def put(self, key: str, value: str, *, collection: str) -> None:
        """Encrypt and store a value."""
        await self._kv.put(key, {"data": value}, collection=collection)
        if key != "__index__":
            idx = set(await self._get_index(collection))
            if key not in idx:
                idx.add(key)
                await self._save_index(collection, builtins.list(idx))

    async def delete(self, key: str, *, collection: str) -> bool:
        """Delete a key. Returns True if the key existed."""
        existed = await self._kv.delete(key, collection=collection)
        if existed and key != "__index__":
            idx = set(await self._get_index(collection))
            idx.discard(key)
            await self._save_index(collection, builtins.list(idx))
        return existed

    async def list(self, prefix: str = "", *, collection: str) -> builtins.list[str]:
        """List all keys matching a prefix within a collection."""
        idx = await self._get_index(collection)
        if prefix:
            return [k for k in idx if k.startswith(prefix)]
        return builtins.list(idx)

    async def check_integrity(self, *, identity: str | None = None) -> bool:
        """Perform a lightweight health check on the underlying store."""
        _ = identity
        try:
            await self._kv.get("__integrity_probe__", collection="__vault_meta__")
            return True
        except Exception:
            return False
