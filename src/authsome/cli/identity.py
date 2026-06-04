"""CLI-owned identity file persistence and runtime resolution."""

from __future__ import annotations

import os
from collections.abc import Mapping
from contextlib import suppress
from enum import StrEnum
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import BaseModel

from authsome.cli.config import load_client_config, save_client_config
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


class IdentitySource(StrEnum):
    """Where the acting runtime identity was resolved from."""

    ENV = "env"
    FILESYSTEM = "filesystem"


class RuntimeIdentity(BaseModel):
    """Resolved acting identity for the current process."""

    handle: str
    did: str
    source: IdentitySource
    signer: Ed25519PrivateKey

    model_config = {"arbitrary_types_allowed": True}


def identities_dir(home: Path) -> Path:
    return get_client_home(home) / "identities"


def identity_metadata_path(home: Path, handle: str) -> Path:
    return identities_dir(home) / f"{handle}.json"


def identity_key_path(home: Path, handle: str) -> Path:
    return identities_dir(home) / f"{handle}.key"


def load_private_key(home: Path, handle: str) -> Ed25519PrivateKey:
    return private_key_from_hex(identity_key_path(home, handle).read_text(encoding="utf-8"))


def load_identity(home: Path, handle: str) -> IdentityMetadata:
    return IdentityMetadata.model_validate_json(identity_metadata_path(home, handle).read_text(encoding="utf-8"))


def identity_exists(home: Path, handle: str) -> bool:
    return identity_metadata_path(home, handle).exists() and identity_key_path(home, handle).exists()


def create_identity(home: Path, handle: str | None = None) -> IdentityMetadata:
    """Create a local identity and private key, returning existing metadata if present."""
    resolved_handle = validate_handle(handle or _unique_handle(home))
    if identity_exists(home, resolved_handle):
        return load_identity(home, resolved_handle)

    directory = identities_dir(home)
    directory.mkdir(parents=True, exist_ok=True)
    with suppress(OSError):
        os.chmod(directory, 0o700)

    material = create_identity_material(resolved_handle)
    key_path = identity_key_path(home, resolved_handle)
    metadata_path = identity_metadata_path(home, resolved_handle)
    key_path.write_text(private_key_to_hex(material.signer) + "\n", encoding="utf-8")
    with suppress(OSError):
        os.chmod(key_path, 0o600)
    metadata_path.write_text(material.metadata.model_dump_json(indent=2), encoding="utf-8")
    _write_active_identity_handle(home, material.metadata.handle)
    return material.metadata


def remove_legacy_default_identity(home: Path) -> None:
    """Remove legacy local files for the implicit default identity."""
    for path in (identity_metadata_path(home, "default"), identity_key_path(home, "default")):
        with suppress(FileNotFoundError):
            path.unlink()


def ensure_local_identity(home: Path, active_handle: str | None = None) -> IdentityMetadata:
    """Return the active local identity, creating one if none exists."""
    remove_legacy_default_identity(home)
    if active_handle is None:
        active_handle = _read_active_identity_handle(home)
    if active_handle:
        if not identity_exists(home, active_handle):
            return create_identity(home, active_handle)
        return load_identity(home, active_handle)
    return create_identity(home)


async def current_from_home(home: Path) -> IdentityMetadata:
    """Return the configured local identity, bootstrapping it if needed."""
    return ensure_local_identity(home)


def load_runtime_identity(home: Path, env: Mapping[str, str] | None = None) -> RuntimeIdentity:
    """Resolve the acting process identity from env or local identity files."""
    handle_override, private_key_hex = _env_identity_values(env)
    if private_key_hex and not handle_override:
        raise ValueError("AUTHSOME_IDENTITY_PRIVATE_KEY requires AUTHSOME_IDENTITY")

    if handle_override and private_key_hex:
        signer = private_key_from_hex(private_key_hex)
        return RuntimeIdentity(
            handle=validate_handle(handle_override),
            did=public_key_to_did_key(signer.public_key()),
            source=IdentitySource.ENV,
            signer=signer,
        )

    identity = ensure_local_identity(home, active_handle=handle_override)
    return RuntimeIdentity(
        handle=identity.handle,
        did=identity.did,
        source=IdentitySource.FILESYSTEM,
        signer=load_private_key(home, identity.handle),
    )


def _read_active_identity_handle(home: Path) -> str | None:
    return load_client_config(home).active_identity


def _write_active_identity_handle(home: Path, handle: str) -> None:
    save_client_config(home, load_client_config(home).model_copy(update={"active_identity": handle}))


def _env_identity_values(env: Mapping[str, str] | None = None) -> tuple[str | None, str | None]:
    values = env if env is not None else os.environ
    handle = values.get("AUTHSOME_IDENTITY", "").strip() or None
    private_key_hex = values.get("AUTHSOME_IDENTITY_PRIVATE_KEY", "").strip() or None
    return handle, private_key_hex


def _unique_handle(home: Path) -> str:
    for _ in range(100):
        handle = generate_handle()
        if not identity_exists(home, handle):
            return handle
    raise RuntimeError("Unable to generate a unique identity handle")
