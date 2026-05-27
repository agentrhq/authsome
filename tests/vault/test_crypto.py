"""Tests for the vault crypto layer.

Only tests our code (MasterSecretResolver, DekManager, AesGcmEncryptionWrapper).
The underlying key-value library's encryption primitives are already well-tested.
"""

from __future__ import annotations

import base64
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest
from key_value.aio.stores.simple import SimpleStore

from authsome.errors import EncryptionUnavailableError
from authsome.vault.crypto import (
    _DEK_KEY,
    _KEY_SIZE,
    _MASTER_KEY_ENV,
    _MASTER_KEY_FILE_ENV,
    _META_COLLECTION,
    AesGcmEncryptionWrapper,
    DekManager,
    MasterSecretResolver,
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


def _stub_keyring(
    monkeypatch: pytest.MonkeyPatch,
    *,
    stored: str | None = None,
    fail_get: bool = False,
    fail_set: bool = False,
) -> dict:
    state: dict = {"stored": stored, "set_calls": []}
    module = ModuleType("keyring")

    def get_password(service, username):
        if fail_get:
            raise OSError("keyring unavailable")
        return state["stored"]

    def set_password(service, username, value):
        if fail_set:
            raise OSError("keyring write failed")
        state["stored"] = value
        state["set_calls"].append(value)

    module.get_password = get_password  # type: ignore[attr-defined]
    module.set_password = set_password  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "keyring", module)
    return state


# ── MasterSecretResolver ──────────────────────────────────────────────────────


class TestMasterSecretResolver:
    def test_env_var_takes_priority(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(_MASTER_KEY_ENV, "from-env")
        _stub_keyring(monkeypatch, stored="from-keyring")
        assert MasterSecretResolver(tmp_path).resolve() == "from-env"

    def test_env_var_strips_whitespace(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(_MASTER_KEY_ENV, "  my-secret  ")
        assert MasterSecretResolver(tmp_path).resolve() == "my-secret"

    def test_default_file_used_when_env_absent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(_MASTER_KEY_ENV, raising=False)
        _stub_keyring(monkeypatch, fail_get=True)
        (tmp_path / "master.key").write_text("from-file", encoding="utf-8")
        assert MasterSecretResolver(tmp_path).resolve() == "from-file"

    def test_custom_file_via_env(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(_MASTER_KEY_ENV, raising=False)
        custom = tmp_path / "custom.key"
        custom.write_text("from-custom", encoding="utf-8")
        monkeypatch.setenv(_MASTER_KEY_FILE_ENV, str(custom))
        _stub_keyring(monkeypatch, fail_get=True)
        assert MasterSecretResolver(tmp_path).resolve() == "from-custom"

    def test_keyring_used_when_file_absent(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(_MASTER_KEY_ENV, raising=False)
        _stub_keyring(monkeypatch, stored="from-keyring")
        assert MasterSecretResolver(tmp_path).resolve() == "from-keyring"

    def test_auto_generates_to_keyring(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(_MASTER_KEY_ENV, raising=False)
        state = _stub_keyring(monkeypatch, stored=None)
        result = MasterSecretResolver(tmp_path).resolve()
        assert result and len(state["set_calls"]) == 1
        assert not (tmp_path / "master.key").exists()

    def test_auto_generates_to_file_when_keyring_unavailable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(_MASTER_KEY_ENV, raising=False)
        _stub_keyring(monkeypatch, fail_get=True, fail_set=True)
        result = MasterSecretResolver(tmp_path).resolve()
        assert (tmp_path / "master.key").read_text(encoding="utf-8").strip() == result

    def test_generated_value_is_stable_across_calls(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv(_MASTER_KEY_ENV, raising=False)
        _stub_keyring(monkeypatch, fail_get=True, fail_set=True)
        r = MasterSecretResolver(tmp_path)
        assert r.resolve() == r.resolve()


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
        monkeypatch.setenv(_MASTER_KEY_ENV, "my-passphrase")
        raw_kv = SimpleStore()
        secret = MasterSecretResolver(tmp_path).resolve()
        dek = await DekManager().load_or_create(secret, raw_kv)
        vault_kv = AesGcmEncryptionWrapper(raw_kv, dek=dek)
        await vault_kv.put("token", {"data": "secret-value"}, collection="creds")
        assert await vault_kv.get("token", collection="creds") == {"data": "secret-value"}

    @pytest.mark.asyncio
    async def test_dek_survives_reload(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(_MASTER_KEY_ENV, "stable-passphrase")
        raw_kv = SimpleStore()
        secret = MasterSecretResolver(tmp_path).resolve()

        dek1 = await DekManager().load_or_create(secret, raw_kv)
        await AesGcmEncryptionWrapper(raw_kv, dek=dek1).put("k", {"data": "v"}, collection="c")

        # Simulate reload: same in-memory store, new DekManager instance
        dek2 = await DekManager().load_or_create(secret, raw_kv)
        result = await AesGcmEncryptionWrapper(raw_kv, dek=dek2).get("k", collection="c")
        assert result == {"data": "v"}
