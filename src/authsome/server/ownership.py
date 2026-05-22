"""Resolve acting identity into principal and vault context."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from authsome.identity.principal import ClaimStatus
from authsome.server.registries import (
    IdentityClaimRegistry,
    PrincipalRegistry,
    PrincipalVaultBindingRegistry,
    VaultRegistry,
)

LOCAL_PRINCIPAL_EMAIL = "local@authsome.internal"


@dataclass(frozen=True)
class ResolvedOwnership:
    """Resolved runtime context for a protected request."""

    identity: str
    principal_id: str
    vault_id: str


class OwnershipResolver(ABC):
    """Resolve principal and vault context for an acting identity."""

    @abstractmethod
    async def resolve(self, *, identity: str) -> ResolvedOwnership:
        """Resolve the principal and vault for an identity."""

    async def claim_identity_for_principal(self, *, identity: str, principal_id: str) -> ResolvedOwnership:
        """Claim an identity for an authenticated principal."""
        raise NotImplementedError


async def ensure_principal_default_vault(
    *,
    principal_id: str,
    vaults: VaultRegistry,
    bindings: PrincipalVaultBindingRegistry,
) -> str:
    """Return the principal's default vault, creating it if needed."""
    binding = await bindings.get_default_vault(principal_id)
    if binding is None:
        vault = await vaults.create_default()
        binding = await bindings.bind_default(principal_id, vault.vault_id)
    return binding.vault_id


class LocalOwnershipResolver(OwnershipResolver):
    """Ownership resolver for local deployments with implicit ownership."""

    def __init__(
        self,
        *,
        principals: PrincipalRegistry,
        vaults: VaultRegistry,
        bindings: PrincipalVaultBindingRegistry,
    ) -> None:
        self._principals = principals
        self._vaults = vaults
        self._bindings = bindings

    async def resolve(self, *, identity: str) -> ResolvedOwnership:
        principal = await self._principals.get_by_email(LOCAL_PRINCIPAL_EMAIL)
        if principal is None:
            principal = await self._principals.create_by_email(LOCAL_PRINCIPAL_EMAIL)
        vault_id = await ensure_principal_default_vault(
            principal_id=principal.principal_id,
            vaults=self._vaults,
            bindings=self._bindings,
        )
        return ResolvedOwnership(identity=identity, principal_id=principal.principal_id, vault_id=vault_id)

    async def claim_identity_for_principal(self, *, identity: str, principal_id: str) -> ResolvedOwnership:
        return await self.resolve(identity=identity)


class HostedOwnershipResolver(OwnershipResolver):
    """Ownership resolver for hosted deployments with explicit claims."""

    def __init__(
        self,
        *,
        principals: PrincipalRegistry,
        vaults: VaultRegistry,
        claims: IdentityClaimRegistry,
        bindings: PrincipalVaultBindingRegistry,
    ) -> None:
        self._principals = principals
        self._vaults = vaults
        self._claims = claims
        self._bindings = bindings

    async def resolve(self, *, identity: str) -> ResolvedOwnership:
        claim = await self._claims.require_claim(identity)
        if claim.claim_status == ClaimStatus.REJECTED:
            raise ValueError(f"Identity '{identity}' claim has been rejected")
        if claim.claim_status != ClaimStatus.ACCEPTED:
            raise ValueError(f"Identity '{identity}' claim is pending principal approval")
        binding = await self._bindings.require_default_vault(claim.principal_id)
        return ResolvedOwnership(identity=identity, principal_id=claim.principal_id, vault_id=binding.vault_id)

    async def claim_identity_for_principal(self, *, identity: str, principal_id: str) -> ResolvedOwnership:
        vault_id = await ensure_principal_default_vault(
            principal_id=principal_id,
            vaults=self._vaults,
            bindings=self._bindings,
        )
        await self._claims.claim_identity(identity, principal_id)
        await self._claims.accept_claim(identity)
        return ResolvedOwnership(identity=identity, principal_id=principal_id, vault_id=vault_id)
