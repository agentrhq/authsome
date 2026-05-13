"""Vault — encrypted key-value layer over AppStore.

The Vault wraps an AppStore's async KV backend and encrypts every value
before writing and decrypts after reading.  It uses collections to
logically separate different data types (profiles, providers, credentials).

The Vault knows nothing about credential types, profiles, or providers.
All key schema decisions belong to the caller (AuthService).
"""

from __future__ import annotations

import builtins
import json
from pathlib import Path
from typing import TYPE_CHECKING

from authsome.store.interfaces import AppStore

if TYPE_CHECKING:
    from authsome.auth.models.config import GlobalConfig
    from authsome.vault.crypto import VaultCrypto


class Vault:
    """Encrypted key-value store backed by an AppStore.

    All values are encrypted at rest using AES-256-GCM.  The master key is
    managed by the configured VaultCrypto backend (local file or OS keyring).

    Config is delegated unencrypted (needed before crypto is available).
    """

    def __init__(
        self,
        app_store: AppStore,
        crypto: VaultCrypto | None = None,
        crypto_mode: str = "local_key",
        master_key_path: Path | None = None,
    ) -> None:
        self._app_store = app_store
        self._crypto = crypto
        self._crypto_mode = crypto_mode
        self._master_key_path = master_key_path

    @property
    def crypto(self) -> VaultCrypto:
        if self._crypto is None:
            from authsome.vault.crypto import create_crypto

            self._crypto = create_crypto(self._master_key_path, self._crypto_mode)
        return self._crypto

    @property
    def home(self) -> Path:
        """Base directory for the storage system."""
        return self._app_store.home

    # ── Config (delegated, unencrypted — bootstrap dependency) ────────────

    async def get_config(self) -> GlobalConfig:
        return await self._app_store.get_config()

    async def save_config(self, config: GlobalConfig) -> None:
        await self._app_store.save_config(config)

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

    async def close(self) -> None:
        """Release resources."""
        await self._app_store.close()

    async def __aenter__(self) -> Vault:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
