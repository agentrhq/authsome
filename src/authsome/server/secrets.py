"""Server-owned secret resolution for root key material."""

from __future__ import annotations

import base64
import os
import secrets
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from authsome.paths import get_server_home

_KEY_SIZE = 32
_KEYRING_SERVICE = "authsome"

MASTER_KEY_ENV = "AUTHSOME_MASTER_KEY"
MASTER_KEY_FILE_ENV = "AUTHSOME_MASTER_KEY_FILE"
UI_SESSION_KEY_ENV = "AUTHSOME_UI_SESSION_KEY"
UI_SESSION_KEY_FILE_ENV = "AUTHSOME_UI_SESSION_KEY_FILE"


@dataclass(frozen=True)
class ServerSecretSpec:
    """Configuration for resolving one server-owned secret."""

    env_var: str
    file_env_var: str
    default_filename: str
    keyring_username: str
    description: str


MASTER_SECRET = ServerSecretSpec(
    env_var=MASTER_KEY_ENV,
    file_env_var=MASTER_KEY_FILE_ENV,
    default_filename="master.key",
    keyring_username="master_key",
    description="master secret",
)

UI_SESSION_SECRET = ServerSecretSpec(
    env_var=UI_SESSION_KEY_ENV,
    file_env_var=UI_SESSION_KEY_FILE_ENV,
    default_filename="ui_session_secret.key",
    keyring_username="ui_session_key",
    description="UI session signing secret",
)


class ServerSecretResolver:
    """Resolve server-owned secrets from env, file, keyring, or generated fallback."""

    def __init__(self, spec: ServerSecretSpec, home: Path | None = None) -> None:
        self._spec = spec
        self._server_home = get_server_home(home)
        self._default_key_file = self._server_home / spec.default_filename

    def resolve(self) -> str:
        value = os.environ.get(self._spec.env_var)
        if value and value.strip():
            return value.strip()

        key_file = self._key_file_path()
        if key_file.exists():
            content = key_file.read_text(encoding="utf-8").strip()
            if content:
                return content

        keyring_value = self._read_keyring()
        if keyring_value:
            return keyring_value

        generated = base64.b64encode(secrets.token_bytes(_KEY_SIZE)).decode("ascii")
        if self._write_keyring(generated):
            logger.info("Generated and stored new {} in OS keyring", self._spec.description)
        else:
            self._write_file(self._default_key_file, generated)
            logger.info("Generated new {} at {}", self._spec.description, self._default_key_file)
        return generated

    def _key_file_path(self) -> Path:
        custom = os.environ.get(self._spec.file_env_var)
        return Path(custom) if custom else self._default_key_file

    def _read_keyring(self) -> str | None:
        try:
            import keyring

            return keyring.get_password(_KEYRING_SERVICE, self._spec.keyring_username)
        except Exception:
            return None

    def _write_keyring(self, value: str) -> bool:
        try:
            import keyring

            keyring.set_password(_KEYRING_SERVICE, self._spec.keyring_username, value)
            return True
        except Exception:
            return False

    def _write_file(self, path: Path, value: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass


def load_master_secret(home: Path | None = None) -> str:
    """Load or create the server-owned vault master secret."""
    return ServerSecretResolver(MASTER_SECRET, home).resolve()


def load_ui_session_signing_secret(home: Path | None = None) -> str:
    """Load or create the server-owned UI session signing secret."""
    return ServerSecretResolver(UI_SESSION_SECRET, home).resolve()
