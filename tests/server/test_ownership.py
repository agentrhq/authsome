from __future__ import annotations

from pathlib import Path

import pytest

from authsome.identity.principal import PrincipalRole
from authsome.server.ownership import OwnershipResolver
from authsome.server.store import create_server_store


@pytest.mark.asyncio
async def test_resolution_maps_accepted_claim_to_principal_default_vault(tmp_path: Path) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        principal = await store.principals.create_by_email("dev@example.com")
        vault = await store.vaults.create_default()
        await store.principal_vault_bindings.bind_default(principal.principal_id, vault.vault_id)
        await store.identity_claims.claim_identity("steady-wisely-boldly-0042", principal.principal_id)
        await store.identity_claims.accept_claim("steady-wisely-boldly-0042")

        resolver = OwnershipResolver(
            principals=store.principals,
            vaults=store.vaults,
            claims=store.identity_claims,
            bindings=store.principal_vault_bindings,
        )
        context = await resolver.resolve(identity="steady-wisely-boldly-0042")

        assert context.principal_id == principal.principal_id
        assert context.vault_id == vault.vault_id
        assert context.role == PrincipalRole.ADMIN
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_resolution_rejects_unclaimed_identity(tmp_path: Path) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        resolver = OwnershipResolver(
            principals=store.principals,
            vaults=store.vaults,
            claims=store.identity_claims,
            bindings=store.principal_vault_bindings,
        )
        with pytest.raises(ValueError):
            await resolver.resolve(identity="steady-wisely-boldly-0042")
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_principal_registry_assigns_first_principal_admin_then_users(tmp_path: Path) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        first = await store.principals.create_by_email("admin@example.com")
        second = await store.principals.create_by_email("user@example.com")

        assert first.role == PrincipalRole.ADMIN
        assert second.role == PrincipalRole.USER
    finally:
        await store.close()
