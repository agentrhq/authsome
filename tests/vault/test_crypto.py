"""Tests for the vault crypto layer."""

import base64
import sys
import uuid
from pathlib import Path
from types import ModuleType

import pytest

import authsome.vault.crypto as vault_crypto
from authsome.vault.crypto import EnvVarCrypto, KeyringCrypto, LocalFileCrypto, _decode, _encode, create_crypto


class TestLocalFileCrypto:
    """Local file crypto backend tests."""

    @pytest.fixture
    def crypto(self, tmp_path: Path) -> LocalFileCrypto:
        return LocalFileCrypto(tmp_path / "master.key")

    def test_encrypt_returns_string(self, crypto: LocalFileCrypto) -> None:
        result = crypto.encrypt("my-secret-token")
        assert isinstance(result, str)
        assert "." in result  # compact format: nonce.ciphertext+tag

    def test_decrypt_roundtrip(self, crypto: LocalFileCrypto) -> None:
        original = "sk-1234567890abcdef"
        encrypted = crypto.encrypt(original)
        decrypted = crypto.decrypt(encrypted)
        assert decrypted == original

    def test_decrypt_empty_string(self, crypto: LocalFileCrypto) -> None:
        original = ""
        encrypted = crypto.encrypt(original)
        decrypted = crypto.decrypt(encrypted)
        assert decrypted == original

    def test_decrypt_unicode(self, crypto: LocalFileCrypto) -> None:
        original = "secret-🔑-тест-密钥"
        encrypted = crypto.encrypt(original)
        decrypted = crypto.decrypt(encrypted)
        assert decrypted == original

    def test_different_encryptions_differ(self, crypto: LocalFileCrypto) -> None:
        e1 = crypto.encrypt("same-value")
        e2 = crypto.encrypt("same-value")
        assert e1 != e2  # different nonces

    def test_key_persistence(self, tmp_path: Path) -> None:
        key_file = tmp_path / "master.key"
        crypto1 = LocalFileCrypto(key_file)
        encrypted = crypto1.encrypt("persist-test")

        crypto2 = LocalFileCrypto(key_file)
        decrypted = crypto2.decrypt(encrypted)
        assert decrypted == "persist-test"

    def test_master_key_file_created(self, tmp_path: Path) -> None:
        _ = LocalFileCrypto(tmp_path / "master.key")
        key_file = tmp_path / "master.key"
        assert key_file.exists()

    def test_source_metadata(self, tmp_path: Path) -> None:
        key_file = tmp_path / "master.key"
        crypto = LocalFileCrypto(key_file)
        assert crypto.source_id == "local_key"
        assert crypto.source_description == f"Local File ({key_file})"

    def test_long_token_roundtrip(self, crypto: LocalFileCrypto) -> None:
        original = "a" * 10000
        encrypted = crypto.encrypt(original)
        decrypted = crypto.decrypt(encrypted)
        assert decrypted == original

    def test_json_load_error(self, tmp_path: Path) -> None:
        from authsome.errors import EncryptionUnavailableError

        key_file = tmp_path / "master.key"
        key_file.write_text("invalid json")
        with pytest.raises(EncryptionUnavailableError, match="Failed to read local key file"):
            LocalFileCrypto(tmp_path / "master.key")

    def test_chmod_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import os

        def mock_chmod(path, mode):
            raise OSError("Mock error")

        monkeypatch.setattr(os, "chmod", mock_chmod)
        # Should not raise
        _ = LocalFileCrypto(tmp_path / "master.key")

    def test_decrypt_malformed_ciphertext(self, crypto: LocalFileCrypto) -> None:
        from authsome.errors import EncryptionUnavailableError

        with pytest.raises(EncryptionUnavailableError, match="Malformed vault ciphertext"):
            crypto.decrypt("no-dot-separator!!!")

    def test_decrypt_bad_base64(self, crypto: LocalFileCrypto) -> None:
        from authsome.errors import EncryptionUnavailableError

        with pytest.raises(EncryptionUnavailableError):
            crypto.decrypt("!@#$.!@#$")

    def test_decrypt_wrong_data(self, crypto: LocalFileCrypto, tmp_path: Path) -> None:
        from authsome.errors import EncryptionUnavailableError

        # Encrypt with one key, try to decrypt with a different key instance
        other_crypto = LocalFileCrypto(tmp_path / "other" / "master.key")
        ct = other_crypto.encrypt("secret")
        with pytest.raises(EncryptionUnavailableError, match="Decryption failed"):
            crypto.decrypt(ct)


class TestKeyringCrypto:
    """OS Keyring crypto backend tests.

    These tests attempt to use the real OS keyring. They may be skipped
    in headless CI environments where no keyring backend is available.
    """

    @pytest.fixture(autouse=True)
    def isolate_keyring_namespace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        suffix = uuid.uuid4().hex
        monkeypatch.setattr(vault_crypto, "_KEYRING_SERVICE", f"authsome-test-{suffix}")
        monkeypatch.setattr(vault_crypto, "_KEYRING_USERNAME", f"master-key-{suffix}")

    @pytest.fixture
    def crypto(self) -> KeyringCrypto:
        try:
            return KeyringCrypto()
        except Exception:
            pytest.skip("OS keyring not available in this environment")

    def test_encrypt_decrypt_roundtrip(self, crypto: KeyringCrypto) -> None:
        original = "keyring-test-secret"
        encrypted = crypto.encrypt(original)
        decrypted = crypto.decrypt(encrypted)
        assert decrypted == original

    def test_encrypt_returns_string(self, crypto: KeyringCrypto) -> None:
        result = crypto.encrypt("test")
        assert isinstance(result, str)
        assert "." in result

    def test_import_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sys.modules, "keyring", None)
        from authsome.errors import EncryptionUnavailableError

        with pytest.raises(EncryptionUnavailableError, match="The 'keyring' package is required"):
            KeyringCrypto()

    def test_get_password_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import keyring

        def mock_get(*args, **kwargs):
            raise Exception("Mock error")

        monkeypatch.setattr(keyring, "get_password", mock_get)
        from authsome.errors import EncryptionUnavailableError

        with pytest.raises(EncryptionUnavailableError, match="Failed to access OS keyring"):
            KeyringCrypto()

    def test_generate_new_keyring_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import keyring

        def mock_get(*args, **kwargs):
            return None

        def mock_set(*args, **kwargs):
            pass

        monkeypatch.setattr(keyring, "get_password", mock_get)
        monkeypatch.setattr(keyring, "set_password", mock_set)
        backend = KeyringCrypto()
        assert backend._aesgcm is not None

    def test_set_password_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import keyring

        def mock_get(*args, **kwargs):
            return None

        def mock_set(*args, **kwargs):
            raise Exception("Mock error")

        monkeypatch.setattr(keyring, "get_password", mock_get)
        monkeypatch.setattr(keyring, "set_password", mock_set)
        from authsome.errors import EncryptionUnavailableError

        with pytest.raises(EncryptionUnavailableError, match="Failed to store master key"):
            KeyringCrypto()


class TestCreateCryptoAutoMode:
    """Auto-mode master-key source resolution tests."""

    @staticmethod
    def _key_b64(fill_byte: int) -> str:
        return base64.b64encode(bytes([fill_byte]) * 32).decode("ascii")

    @staticmethod
    def _stub_keyring(
        monkeypatch: pytest.MonkeyPatch,
        *,
        existing_key: str | None = None,
        set_password_side_effect: Exception | None = None,
    ) -> dict[str, list[str]]:
        state: dict[str, list[str]] = {"set_calls": []}
        module = ModuleType("keyring")

        def get_password(service: str, username: str) -> str | None:
            _ = (service, username)
            return existing_key

        def set_password(service: str, username: str, value: str) -> None:
            _ = (service, username)
            if set_password_side_effect is not None:
                raise set_password_side_effect
            state["set_calls"].append(value)

        module.get_password = get_password  # type: ignore[attr-defined]
        module.set_password = set_password  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "keyring", module)
        return state

    def test_auto_prefers_env_var(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTHSOME_MASTER_KEY", self._key_b64(1))
        self._stub_keyring(monkeypatch, existing_key=self._key_b64(2))

        crypto = create_crypto(tmp_path / "master.key", "auto")

        assert isinstance(crypto, EnvVarCrypto)
        assert crypto.source_id == "env"
        assert not (tmp_path / "master.key").exists()

    def test_auto_prefers_existing_keyring_key(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        local = LocalFileCrypto(tmp_path / "master.key")
        local_ciphertext = local.encrypt("from-local-file")
        self._stub_keyring(monkeypatch, existing_key=self._key_b64(3))

        crypto = create_crypto(tmp_path / "master.key", "auto")

        assert isinstance(crypto, KeyringCrypto)
        assert crypto.source_id == "keyring"
        from authsome.errors import EncryptionUnavailableError

        with pytest.raises(EncryptionUnavailableError, match="Decryption failed"):
            crypto.decrypt(local_ciphertext)

    def test_auto_preserves_existing_local_file_before_creating_keyring(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        local = LocalFileCrypto(tmp_path / "master.key")
        ciphertext = local.encrypt("keep-using-local-file")
        keyring_state = self._stub_keyring(monkeypatch, existing_key=None)

        crypto = create_crypto(tmp_path / "master.key", "auto")

        assert isinstance(crypto, LocalFileCrypto)
        assert crypto.source_id == "local_key"
        assert crypto.decrypt(ciphertext) == "keep-using-local-file"
        assert keyring_state["set_calls"] == []

    def test_auto_creates_keyring_key_for_fresh_install(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        keyring_state = self._stub_keyring(monkeypatch, existing_key=None)

        crypto = create_crypto(tmp_path / "master.key", "auto")

        assert isinstance(crypto, KeyringCrypto)
        assert crypto.source_id == "keyring"
        assert len(keyring_state["set_calls"]) == 1
        assert not (tmp_path / "master.key").exists()

    def test_auto_falls_back_to_local_file_when_keyring_unavailable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "keyring", None)

        crypto = create_crypto(tmp_path / "master.key", "auto")

        assert isinstance(crypto, LocalFileCrypto)
        assert crypto.source_id == "local_key"
        assert (tmp_path / "master.key").exists()

    def test_env_var_rejects_invalid_key(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AUTHSOME_MASTER_KEY", base64.b64encode(b"too-short").decode("ascii"))
        from authsome.errors import EncryptionUnavailableError

        with pytest.raises(EncryptionUnavailableError, match="must decode to 32 bytes"):
            create_crypto(tmp_path / "master.key", "auto")


class TestVaultCryptoHelpers:
    """Test _encode/_decode helpers."""

    def test_encode_decode_roundtrip(self) -> None:
        nonce = b"\x00" * 12
        ct = b"\xff" * 32
        token = _encode(nonce, ct)
        assert "." in token
        decoded_nonce, decoded_ct = _decode(token)
        assert decoded_nonce == nonce
        assert decoded_ct == ct

    def test_decode_malformed_raises(self) -> None:
        from authsome.errors import EncryptionUnavailableError

        with pytest.raises(EncryptionUnavailableError, match="Malformed vault ciphertext"):
            _decode("no-dot-here")
