from __future__ import annotations

from pathlib import Path

import pytest

from authsome.server.ownership import (
    LOCAL_PRINCIPAL_EMAIL,
    HostedOwnershipResolver,
    LocalOwnershipResolver,
)
from authsome.server.store import create_server_store


@pytest.mark.asyncio
async def test_hosted_resolution_maps_identity_to_default_vault(tmp_path: Path) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        principal = await store.principals.create_by_email("dev@example.com")
        vault = await store.vaults.create_default()
        await store.principal_vault_bindings.bind_default(principal.principal_id, vault.vault_id)
        await store.identity_claims.claim_identity("steady-wisely-boldly-0042", principal.principal_id)
        await store.identity_claims.accept_claim("steady-wisely-boldly-0042")

        resolver = HostedOwnershipResolver(
            principals=store.principals,
            vaults=store.vaults,
            claims=store.identity_claims,
            bindings=store.principal_vault_bindings,
        )
        context = await resolver.resolve(identity="steady-wisely-boldly-0042")

        assert context.principal_id == principal.principal_id
        assert context.vault_id == vault.vault_id
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_local_resolution_creates_implicit_principal_and_vault(tmp_path: Path) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        resolver = LocalOwnershipResolver(
            principals=store.principals,
            vaults=store.vaults,
            bindings=store.principal_vault_bindings,
        )
        context = await resolver.resolve(identity="steady-wisely-boldly-0042")

        principal = await store.principals.get(context.principal_id)
        binding = await store.principal_vault_bindings.get_default_vault(context.principal_id)

        assert principal is not None
        assert principal.email == LOCAL_PRINCIPAL_EMAIL
        assert binding is not None
        assert binding.vault_id == context.vault_id
    finally:
        await store.close()
