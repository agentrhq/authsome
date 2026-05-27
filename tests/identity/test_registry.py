from __future__ import annotations

from pathlib import Path

import pytest

from authsome.identity.principal import ClaimStatus
from authsome.server.store import ServerStore, create_server_store
from authsome.server.store.repositories import IdentityClaimRegistry


async def _store(tmp_path: Path) -> ServerStore:
    return await create_server_store(home=tmp_path)


@pytest.mark.asyncio
async def test_claim_creates_principal_and_default_vault(tmp_path: Path) -> None:
    store = await _store(tmp_path)
    principals = store.principals
    claims = store.identity_claims
    vaults = store.vaults
    bindings = store.principal_vault_bindings

    try:
        principal = await principals.create_by_email("dev@example.com")
        vault = await vaults.create_default()
        binding = await bindings.bind_default(principal.principal_id, vault.vault_id)
        claim = await claims.claim_identity("steady-wisely-boldly-0042", principal.principal_id)

        assert principal.email == "dev@example.com"
        assert vault.handle == "default"
        assert binding.is_default is True
        assert claim.identity_handle == "steady-wisely-boldly-0042"
        assert claim.claim_status == ClaimStatus.PENDING
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_claim_is_immutable_for_existing_identity(tmp_path: Path) -> None:
    store = await _store(tmp_path)
    claims: IdentityClaimRegistry = store.identity_claims

    try:
        principal = await store.principals.create_by_email("dev@example.com")
        other = await store.principals.create_by_email("ops@example.com")
        await claims.claim_identity("steady-wisely-boldly-0042", principal.principal_id)

        with pytest.raises(ValueError, match="already claimed"):
            await claims.claim_identity("steady-wisely-boldly-0042", other.principal_id)
    finally:
        await store.close()
