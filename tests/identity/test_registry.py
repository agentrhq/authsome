from __future__ import annotations

from pathlib import Path

import pytest

from authsome.identity.principal import (
    ClaimStatus,
    IdentityClaimRegistry,
    PrincipalRegistry,
    PrincipalVaultBindingRegistry,
    VaultRegistry,
)


@pytest.mark.asyncio
async def test_claim_creates_principal_and_default_vault(tmp_path: Path) -> None:
    principals = PrincipalRegistry(tmp_path / "principals.json")
    claims = IdentityClaimRegistry(tmp_path / "claims.json")
    vaults = VaultRegistry(tmp_path / "vaults.json")
    bindings = PrincipalVaultBindingRegistry(tmp_path / "bindings.json")

    principal = await principals.get_or_create_by_email("dev@example.com")
    vault = await vaults.create_default()
    binding = await bindings.bind_default(principal.principal_id, vault.vault_id)
    claim = await claims.claim_identity("steady-wisely-boldly-0042", principal.principal_id)

    assert principal.email == "dev@example.com"
    assert vault.handle == "default"
    assert binding.is_default is True
    assert claim.identity_handle == "steady-wisely-boldly-0042"
    assert claim.claim_status == ClaimStatus.PENDING


@pytest.mark.asyncio
async def test_claim_is_immutable_for_existing_identity(tmp_path: Path) -> None:
    claims = IdentityClaimRegistry(tmp_path / "claims.json")
    await claims.claim_identity("steady-wisely-boldly-0042", "principal_1")

    with pytest.raises(ValueError, match="already claimed"):
        await claims.claim_identity("steady-wisely-boldly-0042", "principal_2")
