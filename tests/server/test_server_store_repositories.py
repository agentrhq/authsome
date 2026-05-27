from __future__ import annotations

import os
from pathlib import Path

import pytest

from authsome.identity.local import create_identity
from authsome.identity.principal import ClaimStatus
from authsome.server.store import create_server_store
from authsome.server.store.repositories import IdentityRegistrationError


@pytest.mark.asyncio
async def test_identity_registry_enforces_handle_and_did_uniqueness(tmp_path: Path) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        did = create_identity(tmp_path / "identities-a", "identity-a").did
        other_did = create_identity(tmp_path / "identities-b", "identity-b").did
        await store.identity_registry.register(handle="steady-wisely-boldly-0042", did=did)

        same = await store.identity_registry.register(handle="steady-wisely-boldly-0042", did=did)
        assert same.did == did

        with pytest.raises(IdentityRegistrationError, match="already registered"):
            await store.identity_registry.register(handle="steady-wisely-boldly-0042", did=other_did)

        with pytest.raises(IdentityRegistrationError, match="DID is already registered"):
            await store.identity_registry.register(handle="rapid-brightly-firmly-0007", did=did)
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_principal_vault_claim_flow(tmp_path: Path) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        principal = await store.principals.create_by_email("Dev@Example.com")
        vault = await store.vaults.create_default()
        binding = await store.principal_vault_bindings.bind_default(principal.principal_id, vault.vault_id)
        claim = await store.identity_claims.claim_identity("steady-wisely-boldly-0042", principal.principal_id)

        assert principal.email == "dev@example.com"
        assert vault.handle == "default"
        assert binding.is_default is True
        assert claim.claim_status == ClaimStatus.PENDING

        accepted = await store.identity_claims.accept_claim("steady-wisely-boldly-0042")
        assert accepted.claim_status == ClaimStatus.ACCEPTED
        assert await store.principal_vault_bindings.require_default_vault(principal.principal_id) == binding
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_repository_contract_on_postgres_when_configured(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    database_url = os.environ.get("AUTHSOME_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("AUTHSOME_TEST_DATABASE_URL is not set")
    monkeypatch.setenv("AUTHSOME_DATABASE_URL", database_url)

    store = await create_server_store(home=tmp_path)
    try:
        principal = await store.principals.create_by_email(f"dev-{tmp_path.name}@example.com")
        assert await store.principals.get(principal.principal_id) == principal
    finally:
        await store.close()
