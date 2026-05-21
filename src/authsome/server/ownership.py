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

    @abstractmethod
    async def ensure_claimed_identity(self, *, identity: str, email: str) -> ResolvedOwnership:
        """Claim an identity and resolve its principal and vault context."""


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
        principal = await self._principals.get_or_create_by_email(LOCAL_PRINCIPAL_EMAIL)
        binding = await self._bindings.get_default_vault(principal.principal_id)
        if binding is None:
            vault = await self._vaults.create_default()
            binding = await self._bindings.bind_default(principal.principal_id, vault.vault_id)
        return ResolvedOwnership(identity=identity, principal_id=principal.principal_id, vault_id=binding.vault_id)

    async def ensure_claimed_identity(self, *, identity: str, email: str) -> ResolvedOwnership:
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

    async def ensure_claimed_identity(self, *, identity: str, email: str) -> ResolvedOwnership:
        principal = await self._principals.get_or_create_by_email(email)
        binding = await self._bindings.get_default_vault(principal.principal_id)
        if binding is None:
            vault = await self._vaults.create_default()
            binding = await self._bindings.bind_default(principal.principal_id, vault.vault_id)
        await self._claims.claim_identity(identity, principal.principal_id)
        await self._claims.accept_claim(identity)
        return ResolvedOwnership(identity=identity, principal_id=principal.principal_id, vault_id=binding.vault_id)
