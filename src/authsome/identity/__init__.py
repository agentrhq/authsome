"""Local identity helpers."""

from __future__ import annotations

from pathlib import Path

from authsome.identity.client_config import ClientConfig, client_config_path, load_client_config, save_client_config
from authsome.identity.keys import (
    IdentityMetadata,
    create_identity,
    ensure_local_identity,
    identities_dir,
    identity_exists,
    identity_key_path,
    identity_metadata_path,
    load_identity,
    load_private_key,
    mark_registered,
    public_key_from_did_key,
    public_key_to_did_key,
    remove_legacy_default_identity,
)


async def current_from_home(home: Path) -> IdentityMetadata:
    """Return the configured local identity, bootstrapping it if needed."""
    return ensure_local_identity(home)


__all__ = [
    "IdentityMetadata",
    "ClientConfig",
    "client_config_path",
    "create_identity",
    "current_from_home",
    "ensure_local_identity",
    "identities_dir",
    "identity_exists",
    "identity_key_path",
    "identity_metadata_path",
    "load_client_config",
    "load_identity",
    "load_private_key",
    "mark_registered",
    "public_key_from_did_key",
    "public_key_to_did_key",
    "remove_legacy_default_identity",
    "save_client_config",
]
