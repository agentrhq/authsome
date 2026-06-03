"""Resolve acting identity into principal and vault context."""

from __future__ import annotations

from dataclasses import dataclass

from authsome import audit
from authsome.identity.principal import ClaimStatus, PrincipalRole
from authsome.server.store.repositories import (
    IdentityClaimRegistry,
    PrincipalRegistry,
    PrincipalVaultBindingRegistry,
    VaultRegistry,
)


@dataclass(frozen=True)
class ResolvedOwnership:
    """Resolved runtime context for a protected request.

    ``identity`` is None for principal-only callers (UI/account flows that
    authenticate via email+password rather than a PoP-signed identity key).
    """

    identity: str | None
    principal_id: str
    vault_id: str
    role: PrincipalRole


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


class OwnershipResolver:
    """Resolve principal and vault context for an acting identity.

    Every identity must be claimed by a principal and the claim accepted before
    vault access is granted. This is the single resolution path for all
    deployments — the claiming principal is authenticated out of band (browser
    email+password), and the first principal created on a server is admin.
    """

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
        principal = await self._principals.get(claim.principal_id)
        if principal is None:
            raise ValueError(f"Principal '{claim.principal_id}' not found")
        binding = await self._bindings.require_default_vault(claim.principal_id)
        return ResolvedOwnership(
            identity=identity,
            principal_id=claim.principal_id,
            vault_id=binding.vault_id,
            role=principal.role,
        )

    async def resolve_for_principal(self, *, principal_id: str) -> ResolvedOwnership | None:
        """Resolve vault context for a principal-only caller (UI/account flows).

        Unlike ``resolve``, this path has no identity claim to validate — the
        caller authenticated via email+password, not a PoP-signed key.
        """
        principal = await self._principals.get(principal_id)
        if principal is None:
            return None
        binding = await self._bindings.get_default_vault(principal_id)
        if binding is None:
            return None
        return ResolvedOwnership(
            identity=None,
            principal_id=principal_id,
            vault_id=binding.vault_id,
            role=principal.role,
        )

    async def claim_identity_for_principal(self, *, identity: str, principal_id: str) -> ResolvedOwnership:
        """Claim an identity for an authenticated principal and accept it."""
        vault_id = await ensure_principal_default_vault(
            principal_id=principal_id,
            vaults=self._vaults,
            bindings=self._bindings,
        )
        await self._claims.claim_identity(identity, principal_id)
        await self._claims.accept_claim(identity)
        principal = await self._principals.get(principal_id)
        if principal is None:
            raise ValueError(f"Principal '{principal_id}' not found")
        audit.emit_event(
            "identity.claimed",
            identity=identity,
            principal_id=principal_id,
            status="success",
        )
        return ResolvedOwnership(identity=identity, principal_id=principal_id, vault_id=vault_id, role=principal.role)
