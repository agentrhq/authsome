"""Tests for the vault rekey / master key rotation functionality."""

from __future__ import annotations

import base64
import json
import secrets
from pathlib import Path

import pytest

from authsome.store.local import LocalAppStore
from authsome.vault import Vault
from authsome.vault.crypto import LocalFileCrypto


@pytest.mark.asyncio
class TestVaultRekey:
    """Vault rekeying tests."""

    async def test_rekey_local_key_mode(self, tmp_path: Path) -> None:
        # 1. Initialize store and vault in local_key mode
        app_store = LocalAppStore(tmp_path)
        await app_store.ensure_initialized()

        master_key_path = tmp_path / "server" / "master.key"
        vault = Vault(
            app_store=app_store,
            crypto_mode="local_key",
            master_key_path=master_key_path,
        )

        # 2. Write some encrypted secrets into different collections
        await vault.put("key1", "secret-value-1", collection="col1")
        await vault.put("key2", "secret-value-2", collection="col1")
        await vault.put("key3", "secret-value-3", collection="col2")

        # 3. Read them back to verify they are decrypted correctly
        assert await vault.get("key1", collection="col1") == "secret-value-1"
        assert await vault.get("key2", collection="col1") == "secret-value-2"
        assert await vault.get("key3", collection="col2") == "secret-value-3"

        # Capture old key bytes
        old_key_data = json.loads(master_key_path.read_text(encoding="utf-8"))
        old_key_bytes = base64.b64decode(old_key_data["key"])

        # 4. Generate a new key and perform rekeying
        new_key_bytes = secrets.token_bytes(32)
        await vault.rekey(new_key_bytes)

        # 5. Read them back with the rekeyed vault
        assert await vault.get("key1", collection="col1") == "secret-value-1"
        assert await vault.get("key2", collection="col1") == "secret-value-2"
        assert await vault.get("key3", collection="col2") == "secret-value-3"

        # 6. Verify that the key file is updated
        new_key_data = json.loads(master_key_path.read_text(encoding="utf-8"))
        updated_key_bytes = base64.b64decode(new_key_data["key"])
        assert updated_key_bytes == new_key_bytes
        assert updated_key_bytes != old_key_bytes

        # 7. Verify that trying to decrypt with old key directly fails
        # Get raw ciphertext from store
        raw_val = await app_store.kv.get("key1", collection="col1")
        assert raw_val is not None
        ciphertext = raw_val["data"]

        old_key_path = tmp_path / "server" / "old-master.key"
        old_key_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "key": base64.b64encode(old_key_bytes).decode("ascii"),
                    "algorithm": "AES-256-GCM",
                    "note": "Local master key for authsome. Protect this file.",
                }
            ),
            encoding="utf-8",
        )
        old_crypto = LocalFileCrypto(old_key_path)
        from authsome.errors import EncryptionUnavailableError

        with pytest.raises(EncryptionUnavailableError):
            old_crypto.decrypt(ciphertext)

        # But new crypto decrypts it successfully!
        new_key_path = tmp_path / "server" / "new-master.key"
        new_key_path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "key": base64.b64encode(new_key_bytes).decode("ascii"),
                    "algorithm": "AES-256-GCM",
                    "note": "Local master key for authsome. Protect this file.",
                }
            ),
            encoding="utf-8",
        )
        new_crypto = LocalFileCrypto(new_key_path)
        assert new_crypto.decrypt(ciphertext) == "secret-value-1"

        await app_store.close()

    async def test_rekey_rejects_env_mode(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        app_store = LocalAppStore(tmp_path)
        await app_store.ensure_initialized()
        monkeypatch.setenv("AUTHSOME_MASTER_KEY", base64.b64encode(secrets.token_bytes(32)).decode("ascii"))

        vault = Vault(app_store=app_store, crypto_mode="env")
        await vault.put("key1", "secret-value-1", collection="col1")

        with pytest.raises(ValueError, match="AUTHSOME_MASTER_KEY"):
            await vault.rekey(secrets.token_bytes(32))

        assert await vault.get("key1", collection="col1") == "secret-value-1"
        await app_store.close()

    async def test_rekey_keyring_mode(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Mock keyring set/get methods
        keyring_store: dict[str, str] = {}

        class MockKeyring:
            @staticmethod
            def set_password(service: str, username: str, password: str) -> None:
                keyring_store[f"{service}:{username}"] = password

            @staticmethod
            def get_password(service: str, username: str) -> str | None:
                return keyring_store.get(f"{service}:{username}")

        import sys

        sys.modules["keyring"] = MockKeyring  # type: ignore

        # 1. Initialize store and vault in keyring mode
        app_store = LocalAppStore(tmp_path)
        await app_store.ensure_initialized()

        # Seed initial key in keyring
        initial_key = secrets.token_bytes(32)
        MockKeyring.set_password(
            "authsome",
            "master_key",
            base64.b64encode(initial_key).decode("ascii"),
        )

        vault = Vault(
            app_store=app_store,
            crypto_mode="keyring",
        )

        # 2. Write some encrypted secrets
        await vault.put("key1", "keyring-secret", collection="col1")
        assert await vault.get("key1", collection="col1") == "keyring-secret"

        # 3. Rekey the vault
        new_key_bytes = secrets.token_bytes(32)
        await vault.rekey(new_key_bytes)

        # 4. Verify keyring is updated and vault can still read the secret
        stored_b64 = MockKeyring.get_password("authsome", "master_key")
        assert stored_b64 is not None
        assert base64.b64decode(stored_b64) == new_key_bytes

        assert await vault.get("key1", collection="col1") == "keyring-secret"

        await app_store.close()
