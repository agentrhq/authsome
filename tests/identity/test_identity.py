from pathlib import Path

import pytest

from authsome.cli.client_config import ClientConfig, load_client_config, save_client_config
from authsome.identity import current_from_home
from authsome.identity.local import (
    IdentitySource,
    IdentityStatus,
    create_identity,
    ensure_local_identity,
    identity_key_path,
    load_runtime_identity,
    mark_claimed,
    mark_registered,
    public_key_from_did_key,
    public_key_to_did_key,
)


@pytest.mark.asyncio
async def test_current_from_home_replaces_legacy_default(tmp_path: Path) -> None:
    identity = await current_from_home(tmp_path)

    assert identity.handle != "default"
    assert identity.did.startswith("did:key:z6Mk")
    assert len(identity.handle.split("-")) == 4


def test_create_identity_writes_private_key_mode_0600(tmp_path: Path) -> None:
    identity = create_identity(tmp_path, "steady-wisely-boldly-0042")
    key_path = identity_key_path(tmp_path, identity.handle)

    assert key_path.exists()
    assert key_path.stat().st_mode & 0o777 == 0o600
    assert load_client_config(tmp_path).active_identity == identity.handle
    assert identity.identity_status == IdentityStatus.UNREGISTERED
    assert identity.registered is False
    assert identity.claimed is False


def test_mark_registered_persists_identity_state(tmp_path: Path) -> None:
    identity = create_identity(tmp_path, "steady-wisely-boldly-0042")

    updated = mark_registered(tmp_path, identity.handle)

    assert updated.identity_status == IdentityStatus.REGISTERED
    assert updated.registered is True
    assert updated.claimed is False


def test_mark_claimed_persists_identity_state(tmp_path: Path) -> None:
    identity = create_identity(tmp_path, "steady-wisely-boldly-0042")

    updated = mark_claimed(tmp_path, identity.handle)

    assert updated.identity_status == IdentityStatus.CLAIMED
    assert updated.claimed is True
    assert ensure_local_identity(tmp_path, active_handle=identity.handle).claimed is True


def test_did_key_roundtrip(tmp_path: Path) -> None:
    identity = create_identity(tmp_path, "steady-wisely-boldly-0042")
    public_key = public_key_from_did_key(identity.did)

    assert public_key_to_did_key(public_key) == identity.did


def test_invalid_did_key_rejected() -> None:
    with pytest.raises(ValueError, match="Only did:key"):
        public_key_from_did_key("did:web:example.com")


def test_ensure_local_identity_creates_configured_handle_when_missing(tmp_path: Path) -> None:
    identity = ensure_local_identity(tmp_path, active_handle="brisk-boldly-clearly-1234")

    assert identity.handle == "brisk-boldly-clearly-1234"
    assert identity_key_path(tmp_path, identity.handle).exists()
    assert load_client_config(tmp_path).active_identity == identity.handle


@pytest.mark.asyncio
async def test_current_from_home_uses_client_side_active_identity(tmp_path: Path) -> None:
    first = create_identity(tmp_path, "steady-wisely-boldly-0042")
    create_identity(tmp_path, "rapid-brightly-firmly-0007")
    save_client_config(tmp_path, ClientConfig(active_identity=first.handle))

    identity = await current_from_home(tmp_path)

    assert identity.handle == first.handle


def test_runtime_identity_uses_env_private_key_without_filesystem(tmp_path: Path) -> None:
    env_identity = create_identity(tmp_path, "steady-wisely-boldly-0042")
    private_key_hex = identity_key_path(tmp_path, env_identity.handle).read_text(encoding="utf-8").strip()

    runtime = load_runtime_identity(
        tmp_path,
        env={
            "AUTHSOME_IDENTITY": "rapid-brightly-firmly-0007",
            "AUTHSOME_IDENTITY_PRIVATE_KEY": private_key_hex,
        },
    )

    assert runtime.handle == "rapid-brightly-firmly-0007"
    assert runtime.source is IdentitySource.ENV
    assert runtime.did.startswith("did:key:z6Mk")


def test_runtime_identity_uses_filesystem_for_handle_override(tmp_path: Path) -> None:
    override_identity = create_identity(tmp_path, "rapid-brightly-firmly-0007")

    runtime = load_runtime_identity(tmp_path, env={"AUTHSOME_IDENTITY": override_identity.handle})

    assert runtime.handle == override_identity.handle
    assert runtime.did == override_identity.did
    assert runtime.source is IdentitySource.FILESYSTEM


def test_runtime_identity_creates_missing_handle_override(tmp_path: Path) -> None:
    runtime = load_runtime_identity(tmp_path, env={"AUTHSOME_IDENTITY": "rapid-brightly-firmly-0007"})

    assert runtime.handle == "rapid-brightly-firmly-0007"
    assert runtime.source is IdentitySource.FILESYSTEM
    assert runtime.did.startswith("did:key:z6Mk")
    assert load_client_config(tmp_path).active_identity == "rapid-brightly-firmly-0007"
    assert identity_key_path(tmp_path, runtime.handle).exists()


def test_runtime_identity_rejects_private_key_without_handle(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="AUTHSOME_IDENTITY"):
        load_runtime_identity(tmp_path, env={"AUTHSOME_IDENTITY_PRIVATE_KEY": "00" * 32})
