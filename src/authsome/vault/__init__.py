"""Vault — encrypted key-value layer over AppStore."""

from __future__ import annotations

import builtins
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from key_value.aio._utils.compound import uncompound_key
from loguru import logger

from authsome.store.interfaces import AppStore
from authsome.vault.crypto import VaultCrypto, create_crypto, create_rekey_crypto

if TYPE_CHECKING:
    from authsome.vault.crypto import VaultCrypto


class Vault:
    """Encrypted key-value store backed by an AppStore.

    All values are encrypted at rest using AES-256-GCM.  The master key is
    managed by the configured VaultCrypto backend (local file or OS keyring).
    """

    def __init__(
        self,
        app_store: AppStore,
        crypto: VaultCrypto | None = None,
        crypto_mode: str = "auto",
        master_key_path: Path | None = None,
    ) -> None:
        self._app_store = app_store
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
        val = await self._app_store.kv.get("__index__", collection=collection)
        if not val:
            return []
        return json.loads(val["data"])

    async def _save_index(self, collection: str, keys: builtins.list[str]) -> None:
        await self._app_store.kv.put("__index__", {"data": json.dumps(sorted(keys))}, collection=collection)

    # ── Encrypted KV interface ────────────────────────────────────────────

    async def get(self, key: str, *, collection: str) -> str | None:
        """Retrieve and decrypt a value. Returns None if key not found."""
        val = await self._app_store.kv.get(key, collection=collection)
        if val is None:
            return None
        return self.crypto.decrypt(val["data"])

    async def put(self, key: str, value: str, *, collection: str) -> None:
        """Encrypt and store a value."""
        encrypted = self.crypto.encrypt(value)
        await self._app_store.kv.put(key, {"data": encrypted}, collection=collection)
        if key != "__index__":
            idx = set(await self._get_index(collection))
            if key not in idx:
                idx.add(key)
                await self._save_index(collection, builtins.list(idx))

    async def delete(self, key: str, *, collection: str) -> bool:
        """Delete a key. Returns True if the key existed."""
        existed = await self._app_store.kv.delete(key, collection=collection)
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
        return await self._app_store.check_integrity()

    async def rekey(self, new_key_bytes: bytes) -> None:
        """Re-encrypt all encrypted keys in the underlying KV store using a new master key."""
        old_crypto = self.crypto
        old_crypto.assert_rekey_supported()

        # 1. Create a new crypto instance using the new key
        new_crypto = create_rekey_crypto(new_key_bytes)

        # 2. Iterate over all entries in the underlying DiskStore cache
        # DiskStore stores compound keys as collection::key
        cache = cast(Any, self._app_store.kv)._cache
        # Collect all keys first to avoid iterating while modifying
        all_compound_keys = list(cache.iterkeys())

        # Perform in-place re-encryption
        reencrypted_count = 0
        for comp_key in all_compound_keys:
            try:
                collection, key = uncompound_key(comp_key)
            except Exception:
                continue

            if collection == "config" or key == "__index__":
                continue

            # Retrieve and decrypt the entry
            val = await self._app_store.kv.get(key, collection=collection)
            if val is not None and "data" in val:
                ciphertext = val["data"]
                # Decrypt with old crypto and re-encrypt with new crypto
                plaintext = old_crypto.decrypt(ciphertext)
                new_ciphertext = new_crypto.encrypt(plaintext)
                # Store the re-encrypted value back
                await self._app_store.kv.put(key, {"data": new_ciphertext}, collection=collection)
                reencrypted_count += 1

        # 3. Delegate persistence to the active backend
        old_crypto.persist_rekeyed_key(new_key_bytes)

        # 4. Clear the active crypto in memory so it reloads on next access
        self._crypto = None
        logger.info("Rekey completed successfully. Re-encrypted {} keys.", reencrypted_count)

    async def close(self) -> None:
        """Release resources."""
        await self._app_store.close()

    async def __aenter__(self) -> Vault:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
