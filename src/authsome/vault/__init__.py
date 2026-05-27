"""Vault — encrypted key-value layer over py-key-value adapters."""

from __future__ import annotations

import builtins
import inspect
import json
from pathlib import Path
from typing import TYPE_CHECKING

from key_value.aio.protocols.key_value import AsyncKeyValue

from authsome.vault.crypto import VaultCrypto, create_crypto

if TYPE_CHECKING:
    from authsome.vault.crypto import VaultCrypto


# TODO: AES-GCM should be a key_value store wrapper ( see FernetWrapper)
# TODO: Add a config for vault ( master.key and crypto mode is property of this wrapper), it should load


class Vault:
    """Encrypted key-value store backed by a py-key-value adapter.

    All values are encrypted at rest using AES-256-GCM.  The master key is
    managed by the configured VaultCrypto backend (local file or OS keyring).
    """

    def __init__(
        self,
        kv: AsyncKeyValue,
        crypto: VaultCrypto | None = None,
        crypto_mode: str = "auto",
        master_key_path: Path | None = None,
    ) -> None:
        self._kv = kv
        self._crypto = crypto
        self._crypto_mode = crypto_mode
        self._master_key_path = master_key_path

    @property
    def crypto(self) -> VaultCrypto:
        if self._crypto is None:
            self._crypto = create_crypto(self._master_key_path, self._crypto_mode)
        return self._crypto

    @property
    def crypto_mode(self) -> str:
        """Configured crypto resolution mode."""
        return self._crypto_mode

    @property
    def crypto_source(self) -> str:
        """Effective crypto source identifier."""
        return self.crypto.source_id

    @property
    def crypto_source_description(self) -> str:
        """Human-readable description of the effective crypto source."""
        return self.crypto.source_description

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
        return self.crypto.decrypt(val["data"])

    async def put(self, key: str, value: str, *, collection: str) -> None:
        """Encrypt and store a value."""
        encrypted = self.crypto.encrypt(value)
        await self._kv.put(key, {"data": encrypted}, collection=collection)
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
        return list(idx)

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def check_integrity(self, *, identity: str | None = None) -> bool:
        """Perform health check on underlying store."""
        _ = identity
        check = getattr(self._kv, "check_integrity", None)
        if not callable(check):
            return True
        result = check()
        if inspect.isawaitable(result):
            return bool(await result)
        return bool(result)

    async def close(self) -> None:
        """Release resources."""
        close = getattr(self._kv, "close", None)
        if callable(close):
            result = close()
            if inspect.isawaitable(result):
                await result

    async def __aenter__(self) -> Vault:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
