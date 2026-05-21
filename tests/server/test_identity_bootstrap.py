from pathlib import Path

import pytest

from authsome.identity import create_identity
from authsome.identity.principal import IdentityClaimRegistry
from authsome.identity.registry import IdentityRegistry
from authsome.server.identity_bootstrap import (
    HostedIdentityBootstrapService,
    LocalIdentityBootstrapService,
)
from authsome.server.ui_sessions import UiSessionStore


@pytest.mark.asyncio
async def test_local_bootstrap_registers_without_claim(tmp_path: Path) -> None:
    identity = create_identity(tmp_path, "steady-wisely-boldly-0042")
    registry = IdentityRegistry(tmp_path / "identity_registry.json")
    service = LocalIdentityBootstrapService(registry=registry)

    status = await service.register_identity(handle=identity.handle, did=identity.did)

    assert status.registration_status == "registered"
    assert status.claim_url == ""


@pytest.mark.asyncio
async def test_hosted_bootstrap_requires_claim_until_identity_is_claimed(tmp_path: Path) -> None:
    identity = create_identity(tmp_path, "steady-wisely-boldly-0042")
    registry = IdentityRegistry(tmp_path / "identity_registry.json")
    claims = IdentityClaimRegistry(tmp_path / "claims.json")
    ui_sessions = UiSessionStore("test-secret")
    service = HostedIdentityBootstrapService(
        registry=registry,
        claims=claims,
        ui_sessions=ui_sessions,
        server_base_url="http://127.0.0.1:7998",
    )

    status = await service.register_identity(handle=identity.handle, did=identity.did)

    assert status.registration_status == "claim_required"
    assert status.claim_url.startswith("http://127.0.0.1:7998/ui/claim/")


@pytest.mark.asyncio
async def test_hosted_bootstrap_returns_claimed_status_after_claim(tmp_path: Path) -> None:
    identity = create_identity(tmp_path, "steady-wisely-boldly-0042")
    registry = IdentityRegistry(tmp_path / "identity_registry.json")
    claims = IdentityClaimRegistry(tmp_path / "claims.json")
    ui_sessions = UiSessionStore("test-secret")
    service = HostedIdentityBootstrapService(
        registry=registry,
        claims=claims,
        ui_sessions=ui_sessions,
        server_base_url="http://127.0.0.1:7998",
    )

    await registry.register(handle=identity.handle, did=identity.did)
    await claims.claim_identity(identity.handle, "principal_123")
    await claims.accept_claim(identity.handle)

    status = await service.get_identity_status(handle=identity.handle)

    assert status is not None
    assert status.registration_status == "claimed"
    assert status.principal_id == "principal_123"
