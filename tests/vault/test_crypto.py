"""Tests for the vault crypto layer.

Only tests our code (DekManager, AesGcmEncryptionWrapper).
The underlying key-value library's encryption primitives are already well-tested.
"""

import base64
import os
from pathlib import Path

import pytest
from key_value.aio.stores.simple import SimpleStore

from authsome.errors import EncryptionUnavailableError
from authsome.server.secrets import MASTER_KEY_ENV, load_master_secret
from authsome.vault.crypto import (
    _DEK_KEY,
    _KEY_SIZE,
    _META_COLLECTION,
    AesGcmEncryptionWrapper,
    DekManager,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def kv() -> SimpleStore:
    return SimpleStore()


@pytest.fixture
def dek() -> bytes:
    return os.urandom(_KEY_SIZE)


def _random_secret() -> str:
    return base64.b64encode(os.urandom(_KEY_SIZE)).decode("ascii")


# ── DekManager ────────────────────────────────────────────────────────────────


class TestDekManager:
    @pytest.mark.asyncio
    async def test_creates_dek_on_first_call(self, kv: SimpleStore) -> None:
        dek = await DekManager().load_or_create("secret", kv)
        assert len(dek) == _KEY_SIZE

    @pytest.mark.asyncio
    async def test_same_dek_returned_on_reload(self, kv: SimpleStore) -> None:
        dek1 = await DekManager().load_or_create("secret", kv)
        dek2 = await DekManager().load_or_create("secret", kv)
        assert dek1 == dek2

    @pytest.mark.asyncio
    async def test_dek_record_stored_in_kv(self, kv: SimpleStore) -> None:
        await DekManager().load_or_create("secret", kv)
        record = await kv.get(_DEK_KEY, collection=_META_COLLECTION)
        assert record is not None and "wrapped_dek" in record and "kdf" in record

    @pytest.mark.asyncio
    async def test_wrong_secret_fails(self, kv: SimpleStore) -> None:
        await DekManager().load_or_create("correct", kv)
        with pytest.raises(EncryptionUnavailableError, match="Failed to unwrap vault DEK"):
            await DekManager().load_or_create("wrong", kv)

    @pytest.mark.asyncio
    async def test_passphrase_and_random_key_both_accepted(self) -> None:
        dek_a = await DekManager().load_or_create("human passphrase", SimpleStore())
        dek_b = await DekManager().load_or_create(_random_secret(), SimpleStore())
        assert len(dek_a) == len(dek_b) == _KEY_SIZE


# ── AesGcmEncryptionWrapper ───────────────────────────────────────────────────


class TestAesGcmEncryptionWrapper:
    def test_rejects_short_dek(self, kv: SimpleStore) -> None:
        with pytest.raises(EncryptionUnavailableError, match="DEK must be"):
            AesGcmEncryptionWrapper(kv, dek=b"tooshort")

    def test_accepts_valid_dek(self, kv: SimpleStore, dek: bytes) -> None:
        assert AesGcmEncryptionWrapper(kv, dek=dek) is not None


# ── Integration ───────────────────────────────────────────────────────────────


class TestVaultBootstrap:
    @pytest.mark.asyncio
    async def test_full_roundtrip(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(MASTER_KEY_ENV, "my-passphrase")
        raw_kv = SimpleStore()
        secret = load_master_secret(tmp_path)
        dek = await DekManager().load_or_create(secret, raw_kv)
        vault_kv = AesGcmEncryptionWrapper(raw_kv, dek=dek)
        await vault_kv.put("token", {"data": "secret-value"}, collection="creds")
        assert await vault_kv.get("token", collection="creds") == {"data": "secret-value"}

    @pytest.mark.asyncio
    async def test_dek_survives_reload(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(MASTER_KEY_ENV, "stable-passphrase")
        raw_kv = SimpleStore()
        secret = load_master_secret(tmp_path)

        dek1 = await DekManager().load_or_create(secret, raw_kv)
        await AesGcmEncryptionWrapper(raw_kv, dek=dek1).put("k", {"data": "v"}, collection="c")

        # Simulate reload: same in-memory store, new DekManager instance
        dek2 = await DekManager().load_or_create(secret, raw_kv)
        result = await AesGcmEncryptionWrapper(raw_kv, dek=dek2).get("k", collection="c")
        assert result == {"data": "v"}
