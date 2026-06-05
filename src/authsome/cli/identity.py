"""CLI-owned identity file persistence and runtime resolution."""

import os
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
from typing import Self

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import BaseModel

from authsome.cli.config import ClientConfig
from authsome.identity.helpers import (
    IdentityMetadata,
    create_identity_material,
    generate_handle,
    private_key_from_hex,
    private_key_to_hex,
    public_key_to_did_key,
    validate_handle,
)
from authsome.paths import get_client_home


class RuntimeIdentity(BaseModel):
    """Resolved acting identity for the current process."""

    handle: str
    did: str
    signer: Ed25519PrivateKey

    model_config = {"arbitrary_types_allowed": True}

    @classmethod
    def from_pkey(cls, handle: str, signer: Ed25519PrivateKey) -> Self:
        return cls(handle=validate_handle(handle), did=public_key_to_did_key(signer.public_key()), signer=signer)

    @classmethod
    def from_filesystem(cls, home: Path, handle: str) -> Self:
        metadata = cls.load_metadata(home, handle)
        return cls(handle=metadata.handle, did=metadata.did, signer=cls.load_private_key(home, handle))

    @classmethod
    def load(cls, home: Path, env: Mapping[str, str] | None = None) -> Self:
        """Resolve the acting process identity from env or local identity files."""
        handle_override, private_key_hex = cls._env_identity_values(env)
        if private_key_hex and not handle_override:
            raise ValueError("AUTHSOME_IDENTITY_PRIVATE_KEY requires AUTHSOME_IDENTITY")

        if handle_override and private_key_hex:
            return cls.from_pkey(handle_override, private_key_from_hex(private_key_hex))

        return cls.ensure_local(home, active_handle=handle_override)

    @classmethod
    async def current_from_home(cls, home: Path) -> Self:
        """Return the configured local identity, bootstrapping it if needed."""
        return cls.ensure_local(home)

    @classmethod
    def ensure_local(cls, home: Path, active_handle: str | None = None) -> Self:
        """Return the active local identity, creating one if none exists."""
        cls.remove_legacy_default(home)
        if active_handle is None:
            active_handle = cls._read_active_identity_handle(home)
        if active_handle:
            if not cls.exists(home, active_handle):
                return cls.create(home, active_handle)
            return cls.from_filesystem(home, active_handle)
        return cls.create(home)

    @classmethod
    def create(cls, home: Path, handle: str | None = None) -> Self:
        """Create a local identity and private key, returning existing files if present."""
        resolved_handle = validate_handle(handle or cls._unique_handle(home))
        if cls.exists(home, resolved_handle):
            return cls.from_filesystem(home, resolved_handle)

        directory = cls.identities_dir(home)
        directory.mkdir(parents=True, exist_ok=True)
        with suppress(OSError):
            os.chmod(directory, 0o700)

        material = create_identity_material(resolved_handle)
        key_path = cls.key_path(home, resolved_handle)
        metadata_path = cls.metadata_path(home, resolved_handle)
        key_path.write_text(private_key_to_hex(material.signer) + "\n", encoding="utf-8")
        with suppress(OSError):
            os.chmod(key_path, 0o600)
        metadata_path.write_text(material.metadata.model_dump_json(indent=2), encoding="utf-8")
        cls._write_active_identity_handle(home, material.metadata.handle)
        return cls(handle=material.metadata.handle, did=material.metadata.did, signer=material.signer)

    @classmethod
    def load_metadata(cls, home: Path, handle: str) -> IdentityMetadata:
        return IdentityMetadata.model_validate_json(cls.metadata_path(home, handle).read_text(encoding="utf-8"))

    @classmethod
    def load_private_key(cls, home: Path, handle: str) -> Ed25519PrivateKey:
        return private_key_from_hex(cls.key_path(home, handle).read_text(encoding="utf-8"))

    @staticmethod
    def identities_dir(home: Path) -> Path:
        return get_client_home(home) / "identities"

    @classmethod
    def metadata_path(cls, home: Path, handle: str) -> Path:
        return cls.identities_dir(home) / f"{handle}.json"

    @classmethod
    def key_path(cls, home: Path, handle: str) -> Path:
        return cls.identities_dir(home) / f"{handle}.key"

    @classmethod
    def exists(cls, home: Path, handle: str) -> bool:
        return cls.metadata_path(home, handle).exists() and cls.key_path(home, handle).exists()

    @classmethod
    def remove_legacy_default(cls, home: Path) -> None:
        """Remove legacy local files for the implicit default identity."""
        for path in (cls.metadata_path(home, "default"), cls.key_path(home, "default")):
            with suppress(FileNotFoundError):
                path.unlink()

    @classmethod
    def _unique_handle(cls, home: Path) -> str:
        for _ in range(100):
            handle = generate_handle()
            if not cls.exists(home, handle):
                return handle
        raise RuntimeError("Unable to generate a unique identity handle")

    @staticmethod
    def _env_identity_values(env: Mapping[str, str] | None = None) -> tuple[str | None, str | None]:
        values = env if env is not None else os.environ
        handle = values.get("AUTHSOME_IDENTITY", "").strip() or None
        private_key_hex = values.get("AUTHSOME_IDENTITY_PRIVATE_KEY", "").strip() or None
        return handle, private_key_hex

    @staticmethod
    def _read_active_identity_handle(home: Path) -> str | None:
        return ClientConfig.load(home).active_identity

    @staticmethod
    def _write_active_identity_handle(home: Path, handle: str) -> None:
        ClientConfig.load(home).model_copy(update={"active_identity": handle}).save(home)
