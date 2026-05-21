from pathlib import Path

import pytest

from authsome.cli.client_config import ClientConfig, load_client_config, save_client_config
from authsome.identity import current_from_home
from authsome.identity.local import (
    IdentityStatus,
    create_identity,
    ensure_local_identity,
    identity_key_path,
    load_private_key,
    mark_claimed,
    mark_registered,
    private_key_to_hex,
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


def test_ensure_local_identity_errors_when_configured_handle_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="brisk-boldly-clearly-1234"):
        ensure_local_identity(tmp_path, active_handle="brisk-boldly-clearly-1234")


@pytest.mark.asyncio
async def test_current_from_home_uses_client_side_active_identity(tmp_path: Path) -> None:
    first = create_identity(tmp_path, "steady-wisely-boldly-0042")
    create_identity(tmp_path, "rapid-brightly-firmly-0007")
    save_client_config(tmp_path, ClientConfig(active_identity=first.handle))

    identity = await current_from_home(tmp_path)

    assert identity.handle == first.handle


def test_ensure_local_identity_prefers_environment_identity(monkeypatch, tmp_path: Path) -> None:
    create_identity(tmp_path, "steady-wisely-boldly-0042")
    monkeypatch.setenv("AUTHSOME_IDENTITY", "rapid-brightly-firmly-0007")
    monkeypatch.setenv(
        "AUTHSOME_IDENTITY_PRIVATE_KEY",
        "02" * 32,
    )

    identity = ensure_local_identity(tmp_path)

    assert identity.handle == "rapid-brightly-firmly-0007"
    assert identity.did.startswith("did:key:z6Mk")
    assert identity.identity_status == IdentityStatus.UNREGISTERED


def test_ensure_local_identity_preserves_local_status_for_matching_env_identity(
    monkeypatch, tmp_path: Path
) -> None:
    identity = create_identity(tmp_path, "rapid-brightly-firmly-0007")
    mark_registered(tmp_path, identity.handle)
    mark_claimed(tmp_path, identity.handle)
    monkeypatch.setenv("AUTHSOME_IDENTITY", identity.handle)
    monkeypatch.setenv(
        "AUTHSOME_IDENTITY_PRIVATE_KEY",
        private_key_to_hex(load_private_key(tmp_path, identity.handle)),
    )

    resolved = ensure_local_identity(tmp_path)

    assert resolved.handle == identity.handle
    assert resolved.claimed is True
    assert resolved.registered is True


def test_load_private_key_prefers_environment_identity_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_IDENTITY", "rapid-brightly-firmly-0007")
    monkeypatch.setenv(
        "AUTHSOME_IDENTITY_PRIVATE_KEY",
        "03" * 32,
    )

    private_key = load_private_key(tmp_path, "rapid-brightly-firmly-0007")

    assert public_key_to_did_key(private_key.public_key()).startswith("did:key:z6Mk")


def test_environment_identity_key_requires_handle(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_IDENTITY_PRIVATE_KEY", "04" * 32)

    with pytest.raises(ValueError, match="AUTHSOME_IDENTITY is not set"):
        ensure_local_identity(tmp_path)


def test_environment_identity_handle_without_private_key_has_clear_error(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_IDENTITY", "calm-clearly-quickly-1216")

    with pytest.raises(ValueError, match="AUTHSOME_IDENTITY_PRIVATE_KEY is not set"):
        ensure_local_identity(tmp_path)
