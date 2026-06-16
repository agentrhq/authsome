# ruff: noqa: PLR2004

from pathlib import Path

import pytest

from authsome.cli.config import ClientConfig
from authsome.cli.identity import RuntimeIdentity
from authsome.identity.helpers import (
    public_key_from_did_key,
    public_key_to_did_key,
)


@pytest.mark.asyncio
async def test_current_from_home_replaces_legacy_default(tmp_path: Path) -> None:
    identity = await RuntimeIdentity.current_from_home(tmp_path)

    assert identity.handle != "default"
    assert identity.did.startswith("did:key:z6Mk")
    assert len(identity.handle.split("-")) == 4


def test_create_identity_writes_private_key_mode_0600(tmp_path: Path) -> None:
    identity = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")
    key_path = RuntimeIdentity.key_path(tmp_path, identity.handle)

    assert key_path.exists()
    assert key_path.stat().st_mode & 0o777 == 0o600
    assert ClientConfig.load(tmp_path).active_identity == identity.handle


def test_did_key_roundtrip(tmp_path: Path) -> None:
    identity = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")
    public_key = public_key_from_did_key(identity.did)

    assert public_key_to_did_key(public_key) == identity.did


def test_invalid_did_key_rejected() -> None:
    with pytest.raises(ValueError, match="Only did:key"):
        public_key_from_did_key("did:web:example.com")


def test_ensure_local_identity_creates_configured_handle_when_missing(tmp_path: Path) -> None:
    identity = RuntimeIdentity.ensure_local(tmp_path, active_handle="brisk-boldly-clearly-1234")

    assert identity.handle == "brisk-boldly-clearly-1234"
    assert RuntimeIdentity.key_path(tmp_path, identity.handle).exists()
    assert ClientConfig.load(tmp_path).active_identity == identity.handle


@pytest.mark.asyncio
async def test_current_from_home_uses_client_side_active_identity(tmp_path: Path) -> None:
    first = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")
    RuntimeIdentity.create(tmp_path, "rapid-brightly-firmly-0007")
    ClientConfig(active_identity=first.handle).save(tmp_path)

    identity = await RuntimeIdentity.current_from_home(tmp_path)

    assert identity.handle == first.handle


def test_runtime_identity_uses_env_private_key_without_filesystem(tmp_path: Path) -> None:
    env_identity = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")
    private_key_hex = RuntimeIdentity.key_path(tmp_path, env_identity.handle).read_text(encoding="utf-8").strip()

    runtime = RuntimeIdentity.load(
        tmp_path,
        env={
            "AUTHSOME_IDENTITY": "rapid-brightly-firmly-0007",
            "AUTHSOME_IDENTITY_PRIVATE_KEY": private_key_hex,
        },
    )

    assert runtime.handle == "rapid-brightly-firmly-0007"
    assert runtime.did.startswith("did:key:z6Mk")


def test_runtime_identity_uses_filesystem_for_handle_override(tmp_path: Path) -> None:
    override_identity = RuntimeIdentity.create(tmp_path, "rapid-brightly-firmly-0007")

    runtime = RuntimeIdentity.load(tmp_path, env={"AUTHSOME_IDENTITY": override_identity.handle})

    assert runtime.handle == override_identity.handle
    assert runtime.did == override_identity.did


def test_runtime_identity_creates_missing_handle_override(tmp_path: Path) -> None:
    runtime = RuntimeIdentity.load(tmp_path, env={"AUTHSOME_IDENTITY": "rapid-brightly-firmly-0007"})

    assert runtime.handle == "rapid-brightly-firmly-0007"
    assert runtime.did.startswith("did:key:z6Mk")
    assert ClientConfig.load(tmp_path).active_identity == "rapid-brightly-firmly-0007"
    assert RuntimeIdentity.key_path(tmp_path, runtime.handle).exists()


def test_runtime_identity_env_private_key_only_defers_handle(tmp_path: Path) -> None:
    source = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")
    private_key_hex = RuntimeIdentity.key_path(tmp_path, source.handle).read_text(encoding="utf-8").strip()

    runtime = RuntimeIdentity.load(tmp_path, env={"AUTHSOME_IDENTITY_PRIVATE_KEY": private_key_hex})

    assert runtime.handle is None
    assert runtime.did == source.did
