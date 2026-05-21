"""Vault encryption backends.

The vault uses AES-256-GCM to encrypt record blobs at rest.
The compact wire format is: base64(nonce) + "." + base64(ciphertext || tag)

Two backends are available:
- LocalFileCrypto: master key stored in ~/.authsome/server/master.key (mode 0600)
- KeyringCrypto: master key stored in the OS keyring
"""

from __future__ import annotations

import base64
import json
import os
import secrets
from abc import ABC, abstractmethod
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from loguru import logger

from authsome.errors import EncryptionUnavailableError

_KEY_SIZE_BYTES = 32  # 256-bit
_NONCE_SIZE_BYTES = 12  # 96-bit for AES-GCM
_KEYRING_SERVICE = "authsome"
_KEYRING_USERNAME = "master_key"
_MASTER_KEY_ENV_VAR = "AUTHSOME_MASTER_KEY"


class VaultCrypto(ABC):
    """Protocol for vault-level encryption backends."""

    @property
    @abstractmethod
    def source_id(self) -> str:
        """Stable identifier for the effective master-key source."""
        ...

    @property
    @abstractmethod
    def source_description(self) -> str:
        """Human-readable description of the effective master-key source."""
        ...

    @abstractmethod
    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext and return a compact ciphertext string."""
        ...

    @abstractmethod
    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a compact ciphertext string and return plaintext."""
        ...

    @abstractmethod
    def persist_rekeyed_key(self, new_key_bytes: bytes) -> None:
        """Persist a newly rotated master key for this backend."""
        ...

    @abstractmethod
    def assert_rekey_supported(self) -> None:
        """Raise when this backend cannot perform an in-place rekey."""
        ...


def _encode(nonce: bytes, ct_with_tag: bytes) -> str:
    """Pack nonce + ciphertext+tag into a single dot-separated base64 string."""
    return base64.b64encode(nonce).decode("ascii") + "." + base64.b64encode(ct_with_tag).decode("ascii")


def _decode(token: str) -> tuple[bytes, bytes]:
    """Unpack a dot-separated base64 string into (nonce, ciphertext+tag)."""
    try:
        nonce_b64, ct_b64 = token.split(".", 1)
        return base64.b64decode(nonce_b64), base64.b64decode(ct_b64)
    except Exception as exc:
        raise EncryptionUnavailableError(f"Malformed vault ciphertext: {exc}") from exc


class _AesGcmCrypto(VaultCrypto):
    """Base class for AES-GCM encryption backends."""

    def __init__(self, master_key: bytes) -> None:
        if len(master_key) != _KEY_SIZE_BYTES:
            raise EncryptionUnavailableError(
                f"Master key must be {_KEY_SIZE_BYTES} bytes after base64 decoding; got {len(master_key)} bytes."
            )
        self._aesgcm = AESGCM(master_key)

    def encrypt(self, plaintext: str) -> str:
        nonce = secrets.token_bytes(_NONCE_SIZE_BYTES)
        ct_with_tag = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return _encode(nonce, ct_with_tag)

    def decrypt(self, ciphertext: str) -> str:
        nonce, ct_with_tag = _decode(ciphertext)
        try:
            return self._aesgcm.decrypt(nonce, ct_with_tag, None).decode("utf-8")
        except Exception as exc:
            raise EncryptionUnavailableError(f"Decryption failed: {exc}") from exc


class LocalFileCrypto(_AesGcmCrypto):
    """AES-256-GCM with master key stored as a local file."""

    def __init__(self, key_file: Path) -> None:
        self._key_file = key_file
        super().__init__(self._load_key())

    @property
    def source_id(self) -> str:
        return "local_key"

    @property
    def source_description(self) -> str:
        return f"Local File ({self._key_file})"

    def _load_key(self) -> bytes:
        if self._key_file.exists():
            try:
                key_data = json.loads(self._key_file.read_text(encoding="utf-8"))
                return _decode_master_key(key_data["key"], f"local key file {self._key_file}")
            except (json.JSONDecodeError, KeyError, ValueError) as exc:
                raise EncryptionUnavailableError(f"Failed to read local key file {self._key_file}: {exc}") from exc

        master_key = _new_master_key()
        self._key_file.parent.mkdir(parents=True, exist_ok=True)
        key_data = {
            "version": 1,
            "key": base64.b64encode(master_key).decode("ascii"),
            "algorithm": "AES-256-GCM",
            "note": "Local master key for authsome. Protect this file.",
        }
        self._key_file.write_text(json.dumps(key_data, indent=2), encoding="utf-8")
        try:
            os.chmod(self._key_file, 0o600)
        except OSError:
            pass
        logger.info("Generated new master key at {}", self._key_file)
        return master_key

    def persist_rekeyed_key(self, new_key_bytes: bytes) -> None:
        """Atomically replace the local master key file after a rekey."""
        _validate_master_key_bytes(new_key_bytes)
        temp_path = self._key_file.with_suffix(".tmp")
        key_data = {
            "version": 1,
            "key": base64.b64encode(new_key_bytes).decode("ascii"),
            "algorithm": "AES-256-GCM",
            "note": "Local master key for authsome. Protect this file.",
        }
        temp_path.write_text(json.dumps(key_data, indent=2), encoding="utf-8")
        try:
            os.chmod(temp_path, 0o600)
        except OSError:
            pass
        temp_path.replace(self._key_file)

    def assert_rekey_supported(self) -> None:
        """Local file storage supports in-place rekey."""
        return None


class KeyringCrypto(_AesGcmCrypto):
    """AES-256-GCM with master key stored in the OS keyring."""

    def __init__(self, master_key: bytes | None = None) -> None:
        super().__init__(master_key or self._load_key())

    @property
    def source_id(self) -> str:
        return "keyring"

    @property
    def source_description(self) -> str:
        return "OS Keyring"

    def _load_key(self) -> bytes:
        master_key = _get_keyring_key(create_if_missing=True, strict=True)
        if master_key is None:
            raise EncryptionUnavailableError("OS keyring is unavailable and no master key could be created.")
        return master_key

    def persist_rekeyed_key(self, new_key_bytes: bytes) -> None:
        """Store a rotated master key in the OS keyring."""
        _validate_master_key_bytes(new_key_bytes)
        key_b64_str = base64.b64encode(new_key_bytes).decode("ascii")
        try:
            import keyring as kr
        except ImportError as exc:
            raise RuntimeError(
                "The 'keyring' package is required for keyring mode. Install it with: pip install keyring"
            ) from exc

        try:
            kr.set_password(_KEYRING_SERVICE, _KEYRING_USERNAME, key_b64_str)
        except Exception as exc:
            raise RuntimeError(f"Failed to store new master key in OS keyring: {exc}") from exc

    def assert_rekey_supported(self) -> None:
        """OS keyring storage supports in-place rekey."""
        return None


class EnvVarCrypto(_AesGcmCrypto):
    """AES-256-GCM with master key supplied via AUTHSOME_MASTER_KEY."""

    def __init__(self) -> None:
        super().__init__(self._load_key())

    @property
    def source_id(self) -> str:
        return "env"

    @property
    def source_description(self) -> str:
        return f"Environment Variable ({_MASTER_KEY_ENV_VAR})"

    def _load_key(self) -> bytes:
        raw_value = os.environ.get(_MASTER_KEY_ENV_VAR)
        if raw_value is None:
            raise EncryptionUnavailableError(f"{_MASTER_KEY_ENV_VAR} is not set.")
        if not raw_value.strip():
            raise EncryptionUnavailableError(f"{_MASTER_KEY_ENV_VAR} is set but empty.")
        return _decode_master_key(raw_value.strip(), _MASTER_KEY_ENV_VAR)

    def persist_rekeyed_key(self, new_key_bytes: bytes) -> None:
        """Reject in-place rekey for externally supplied master keys."""
        _ = new_key_bytes
        self.assert_rekey_supported()

    def assert_rekey_supported(self) -> None:
        """Reject rekey for externally managed master keys."""
        raise ValueError(
            "Vault rekey is unavailable while using AUTHSOME_MASTER_KEY. "
            "Update the external master key and migrate data from a writable backend first."
        )


def _new_master_key() -> bytes:
    """Generate a new 256-bit master key."""
    return secrets.token_bytes(_KEY_SIZE_BYTES)


def _validate_master_key_bytes(master_key: bytes) -> None:
    """Validate already-decoded master key bytes."""
    if len(master_key) != _KEY_SIZE_BYTES:
        raise EncryptionUnavailableError(f"Master key must be {_KEY_SIZE_BYTES} bytes; got {len(master_key)} bytes.")


def _decode_master_key(encoded_value: str, source: str) -> bytes:
    """Decode and validate a base64-encoded master key."""
    try:
        master_key = base64.b64decode(encoded_value, validate=True)
    except (ValueError, TypeError) as exc:
        raise EncryptionUnavailableError(f"Failed to decode master key from {source}: {exc}") from exc
    if len(master_key) != _KEY_SIZE_BYTES:
        raise EncryptionUnavailableError(
            f"Master key from {source} must decode to {_KEY_SIZE_BYTES} bytes; got {len(master_key)} bytes."
        )
    return master_key


def _get_keyring_key(*, create_if_missing: bool, strict: bool) -> bytes | None:
    """Load a key from the OS keyring, optionally creating it when absent."""
    try:
        import keyring as kr
    except ImportError as exc:
        if strict:
            raise EncryptionUnavailableError(
                "The 'keyring' package is required for keyring mode. Install it with: pip install keyring"
            ) from exc
        return None

    try:
        key_b64 = kr.get_password(_KEYRING_SERVICE, _KEYRING_USERNAME)
    except Exception as exc:
        if strict:
            raise EncryptionUnavailableError(
                f"Failed to access OS keyring: {exc}. Use encryption mode 'local_key' for headless environments."
            ) from exc
        return None

    if key_b64:
        return _decode_master_key(key_b64, "OS keyring")
    if not create_if_missing:
        return None

    master_key = _new_master_key()
    key_b64_str = base64.b64encode(master_key).decode("ascii")
    try:
        kr.set_password(_KEYRING_SERVICE, _KEYRING_USERNAME, key_b64_str)
    except Exception as exc:
        if strict:
            raise EncryptionUnavailableError(
                f"Failed to store master key in OS keyring: {exc}. "
                "Use encryption mode 'local_key' for headless environments."
            ) from exc
        return None
    logger.info("Generated and stored new master key in OS keyring")
    return master_key


def _has_env_master_key() -> bool:
    """Return whether AUTHSOME_MASTER_KEY is present in the environment."""
    return _MASTER_KEY_ENV_VAR in os.environ


def _create_auto_crypto(key_file: Path | None) -> VaultCrypto:
    """Resolve master keys by strength while preserving existing local installs."""
    if _has_env_master_key():
        return EnvVarCrypto()

    existing_keyring_key = _get_keyring_key(create_if_missing=False, strict=False)
    if existing_keyring_key is not None:
        return KeyringCrypto(existing_keyring_key)

    if key_file is None:
        raise ValueError("key_file is required for auto mode fallback")
    if key_file.exists():
        return LocalFileCrypto(key_file)

    created_keyring_key = _get_keyring_key(create_if_missing=True, strict=False)
    if created_keyring_key is not None:
        return KeyringCrypto(created_keyring_key)

    return LocalFileCrypto(key_file)


def create_rekey_crypto(new_key_bytes: bytes) -> VaultCrypto:
    """Create an ephemeral in-memory backend for vault re-encryption."""

    class _RekeyCrypto(_AesGcmCrypto):
        @property
        def source_id(self) -> str:
            return "rekey"

        @property
        def source_description(self) -> str:
            return "In-memory rekey backend"

        def persist_rekeyed_key(self, new_key_bytes: bytes) -> None:
            _ = new_key_bytes
            raise RuntimeError("In-memory rekey backend cannot persist master keys")

        def assert_rekey_supported(self) -> None:
            """This helper backend is never used as a persisted store."""
            raise RuntimeError("In-memory rekey backend cannot validate persisted rekey support")

    return _RekeyCrypto(new_key_bytes)


def create_crypto(key_file: Path | None, mode: str = "auto") -> VaultCrypto:
    """Factory: return the appropriate VaultCrypto backend for the given mode."""
    if mode == "auto":
        return _create_auto_crypto(key_file)
    if mode == "keyring":
        return KeyringCrypto()
    if mode == "env":
        return EnvVarCrypto()
    if key_file is None:
        raise ValueError("key_file is required for 'local_key' mode")
    return LocalFileCrypto(key_file)
