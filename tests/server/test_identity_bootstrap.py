from pathlib import Path

import pytest

from authsome.identity import create_identity
from authsome.server.identity_bootstrap import IdentityBootstrapService
from authsome.server.store import create_server_store
from authsome.server.ui_sessions import UiSessionStore


@pytest.mark.asyncio
async def test_bootstrap_requires_claim_until_identity_is_claimed(tmp_path: Path) -> None:
    identity = create_identity(tmp_path, "steady-wisely-boldly-0042")
    store = await create_server_store(home=tmp_path)
    ui_sessions = UiSessionStore("test-secret")
    service = IdentityBootstrapService(
        registry=store.identity_registry,
        claims=store.identity_claims,
        ui_sessions=ui_sessions,
        server_base_url="http://127.0.0.1:7998",
    )

    try:
        status = await service.register_identity(handle=identity.handle, did=identity.did)

        assert status.registration_status == "claim_required"
        assert status.claim_url.startswith("http://127.0.0.1:7998/claim/")
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_bootstrap_returns_claimed_status_after_claim(tmp_path: Path) -> None:
    identity = create_identity(tmp_path, "steady-wisely-boldly-0042")
    store = await create_server_store(home=tmp_path)
    ui_sessions = UiSessionStore("test-secret")
    service = IdentityBootstrapService(
        registry=store.identity_registry,
        claims=store.identity_claims,
        ui_sessions=ui_sessions,
        server_base_url="http://127.0.0.1:7998",
    )

    try:
        await store.identity_registry.register(handle=identity.handle, did=identity.did)
        principal = await store.principals.create_by_email("dev@example.com")
        await store.identity_claims.claim_identity(identity.handle, principal.principal_id)
        await store.identity_claims.accept_claim(identity.handle)

        status = await service.get_identity_status(handle=identity.handle)

        assert status is not None
        assert status.registration_status == "claimed"
        assert status.principal_id == principal.principal_id
    finally:
        await store.close()
