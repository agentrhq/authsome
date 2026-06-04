"""Vault encryption — AES-256-GCM wrapper over AsyncKeyValue.

Key hierarchy:
  master_secret (env → file → keyring → auto-generate)
      → Argon2id(master_secret, salt) → KEK
      → AES-256-GCM.decrypt(KEK, wrapped_dek) → DEK  [in memory only]
      → AES-256-GCM(DEK, value) → encrypted blob in KV store

The wrapped DEK lives in the KV store under collection=_META_COLLECTION, key=_DEK_KEY.
That collection is accessed directly (unencrypted) — the wrapped DEK is already
protected by AES-256-GCM with the KEK; stealing it without the master secret is useless.
"""

import base64
import secrets
from typing import Any

import argon2.low_level
from argon2 import Type as Argon2Type
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from key_value.aio.protocols.key_value import AsyncKeyValue
from key_value.aio.wrappers.encryption.base import BaseEncryptionWrapper
from loguru import logger

from authsome.errors import EncryptionUnavailableError

_NONCE_SIZE = 12  # 96-bit for AES-GCM
_KEY_SIZE = 32  # 256-bit

_META_COLLECTION = "__vault_meta__"
_DEK_KEY = "__dek__"

_ARGON2_MEMORY_COST = 65536  # 64 MB
_ARGON2_TIME_COST = 3
_ARGON2_PARALLELISM = 4

ENCRYPTION_VERSION = 1


class DekManager:
    """Bootstraps and loads the vault DEK from the raw (unencrypted) KV store.

    The DEK record is stored in _META_COLLECTION and contains the Argon2id parameters,
    the salt, and the AES-256-GCM-wrapped DEK. It is NOT re-encrypted by the
    AesGcmEncryptionWrapper — the KEK wrapping is the protection layer.
    """

    async def load_or_create(self, master_secret: str, kv: AsyncKeyValue) -> bytes:
        """Return the DEK, creating and persisting a new one if none exists."""
        record = await kv.get(_DEK_KEY, collection=_META_COLLECTION)
        if record is not None:
            return self._unwrap(master_secret, record)
        return await self._create(master_secret, kv)

    def _derive_kek(self, master_secret: str, salt: bytes) -> bytes:
        return argon2.low_level.hash_secret_raw(
            secret=master_secret.encode("utf-8"),
            salt=salt,
            time_cost=_ARGON2_TIME_COST,
            memory_cost=_ARGON2_MEMORY_COST,
            parallelism=_ARGON2_PARALLELISM,
            hash_len=_KEY_SIZE,
            type=Argon2Type.ID,
        )

    def _unwrap(self, master_secret: str, record: dict[str, Any]) -> bytes:
        try:
            salt = base64.b64decode(record["kdf"]["salt"])
            kek = self._derive_kek(master_secret, salt)
            nonce = base64.b64decode(record["wrapped_dek"]["nonce"])
            ct = base64.b64decode(record["wrapped_dek"]["ciphertext"])
            return AESGCM(kek).decrypt(nonce, ct, None)
        except Exception as exc:
            raise EncryptionUnavailableError(f"Failed to unwrap vault DEK: {exc}") from exc

    async def _create(self, master_secret: str, kv: AsyncKeyValue) -> bytes:
        salt = secrets.token_bytes(16)
        dek = secrets.token_bytes(_KEY_SIZE)
        kek = self._derive_kek(master_secret, salt)
        nonce = secrets.token_bytes(_NONCE_SIZE)
        wrapped = AESGCM(kek).encrypt(nonce, dek, None)
        record: dict[str, Any] = {
            "version": ENCRYPTION_VERSION,
            "kdf": {
                "alg": "argon2id",
                "salt": base64.b64encode(salt).decode("ascii"),
                "memory_cost": _ARGON2_MEMORY_COST,
                "time_cost": _ARGON2_TIME_COST,
                "parallelism": _ARGON2_PARALLELISM,
            },
            "wrapped_dek": {
                "alg": "AES-256-GCM",
                "nonce": base64.b64encode(nonce).decode("ascii"),
                "ciphertext": base64.b64encode(wrapped).decode("ascii"),
            },
        }
        await kv.put(_DEK_KEY, record, collection=_META_COLLECTION)
        logger.info("Created and stored new vault DEK")
        return dek


def _aes_gcm_encrypt(aesgcm: AESGCM, data: bytes) -> bytes:
    """Encrypt data with a fresh nonce; returns nonce + ciphertext-with-tag."""
    nonce = secrets.token_bytes(_NONCE_SIZE)
    return nonce + aesgcm.encrypt(nonce, data, None)


def _aes_gcm_decrypt(aesgcm: AESGCM, data: bytes, version: int) -> bytes:
    if version > ENCRYPTION_VERSION:
        raise EncryptionUnavailableError(f"Unsupported encryption version: {version}")
    nonce, ct = data[:_NONCE_SIZE], data[_NONCE_SIZE:]
    try:
        return aesgcm.decrypt(nonce, ct, None)
    except Exception as exc:
        raise EncryptionUnavailableError(f"Decryption failed: {exc}") from exc


class AesGcmEncryptionWrapper(BaseEncryptionWrapper):
    """AES-256-GCM encryption wrapper — drop-in replacement for FernetEncryptionWrapper.

    Follows the same BaseEncryptionWrapper pattern: values are JSON-serialised,
    encrypted, base64-encoded, and stored as {"__encrypted_data__": ..., "__encryption_version__": 1}.
    """

    def __init__(
        self,
        key_value: AsyncKeyValue,
        *,
        dek: bytes,
        raise_on_decryption_error: bool = True,
    ) -> None:
        if len(dek) != _KEY_SIZE:
            raise EncryptionUnavailableError(f"DEK must be {_KEY_SIZE} bytes; got {len(dek)}")
        aesgcm = AESGCM(dek)
        super().__init__(
            key_value=key_value,
            encryption_fn=lambda data: _aes_gcm_encrypt(aesgcm, data),
            decryption_fn=lambda data, version: _aes_gcm_decrypt(aesgcm, data, version),
            encryption_version=ENCRYPTION_VERSION,
            raise_on_decryption_error=raise_on_decryption_error,
        )
