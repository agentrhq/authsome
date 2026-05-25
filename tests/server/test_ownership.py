from __future__ import annotations

from pathlib import Path

import pytest

from authsome.server.ownership import (
    LOCAL_PRINCIPAL_EMAIL,
    HostedOwnershipResolver,
    LocalOwnershipResolver,
)
from authsome.server.registries import (
    IdentityClaimRegistry,
    PrincipalRegistry,
    PrincipalVaultBindingRegistry,
    VaultRegistry,
)


@pytest.mark.asyncio
async def test_hosted_resolution_maps_identity_to_default_vault(tmp_path: Path) -> None:
    principals = PrincipalRegistry(tmp_path / "principals.json")
    claims = IdentityClaimRegistry(tmp_path / "claims.json")
    vaults = VaultRegistry(tmp_path / "vaults.json")
    bindings = PrincipalVaultBindingRegistry(tmp_path / "bindings.json")
    principal = await principals.create_by_email("dev@example.com")
    vault = await vaults.create_default()
    await bindings.bind_default(principal.principal_id, vault.vault_id)
    await claims.claim_identity("steady-wisely-boldly-0042", principal.principal_id)
    await claims.accept_claim("steady-wisely-boldly-0042")

    resolver = HostedOwnershipResolver(
        principals=principals,
        vaults=vaults,
        claims=claims,
        bindings=bindings,
    )
    context = await resolver.resolve(identity="steady-wisely-boldly-0042")

    assert context.principal_id == principal.principal_id
    assert context.vault_id == vault.vault_id


@pytest.mark.asyncio
async def test_local_resolution_creates_implicit_principal_and_vault(tmp_path: Path) -> None:
    principals = PrincipalRegistry(tmp_path / "principals.json")
    vaults = VaultRegistry(tmp_path / "vaults.json")
    bindings = PrincipalVaultBindingRegistry(tmp_path / "bindings.json")

    resolver = LocalOwnershipResolver(
        principals=principals,
        vaults=vaults,
        bindings=bindings,
    )
    context = await resolver.resolve(identity="steady-wisely-boldly-0042")

    principal = await principals.get(context.principal_id)
    binding = await bindings.get_default_vault(context.principal_id)

    assert principal is not None
    assert principal.email == LOCAL_PRINCIPAL_EMAIL
    assert binding is not None
    assert binding.vault_id == context.vault_id
