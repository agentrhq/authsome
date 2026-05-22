"""Deployment-specific identity bootstrap behavior."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from authsome.identity.principal import ClaimStatus
from authsome.identity.registry import IdentityRegistration
from authsome.server.registries import IdentityClaimRegistry, IdentityRegistry
from authsome.server.ui_sessions import UiSessionStore


@dataclass(frozen=True)
class IdentityBootstrapStatus:
    """Normalized identity bootstrap result returned to API routes."""

    identity: str
    did: str
    registration_status: str
    principal_id: str = ""
    claim_url: str = ""

    def to_payload(self) -> dict[str, str]:
        """Serialize a route payload without exposing deployment-specific logic."""
        payload = {
            "status": "registered",
            "identity": self.identity,
            "did": self.did,
            "registration_status": self.registration_status,
        }
        if self.principal_id:
            payload["principal_id"] = self.principal_id
        if self.claim_url:
            payload["claim_url"] = self.claim_url
        return payload


class IdentityBootstrapService(ABC):
    """Register identities and report their readiness state."""

    def __init__(self, *, registry: IdentityRegistry) -> None:
        self._registry = registry

    async def register_identity(self, *, handle: str, did: str) -> IdentityBootstrapStatus:
        registration = await self._registry.register(handle=handle, did=did)
        return await self._build_status(registration)

    async def get_identity_status(self, *, handle: str) -> IdentityBootstrapStatus | None:
        registration = await self._registry.resolve(handle)
        if registration is None:
            return None
        return await self._build_status(registration)

    @abstractmethod
    async def _build_status(self, registration: IdentityRegistration) -> IdentityBootstrapStatus:
        """Return a normalized readiness status for a registered identity."""


class LocalIdentityBootstrapService(IdentityBootstrapService):
    """Bootstrap service for local deployments with implicit ownership."""

    async def _build_status(self, registration: IdentityRegistration) -> IdentityBootstrapStatus:
        return IdentityBootstrapStatus(
            identity=registration.handle,
            did=registration.did,
            registration_status="registered",
        )


class HostedIdentityBootstrapService(IdentityBootstrapService):
    """Bootstrap service for hosted deployments requiring explicit claims."""

    def __init__(
        self,
        *,
        registry: IdentityRegistry,
        claims: IdentityClaimRegistry,
        ui_sessions: UiSessionStore,
        server_base_url: str,
    ) -> None:
        super().__init__(registry=registry)
        self._claims = claims
        self._ui_sessions = ui_sessions
        self._server_base_url = server_base_url.rstrip("/")

    async def _build_status(self, registration: IdentityRegistration) -> IdentityBootstrapStatus:
        claim = await self._claims.resolve(registration.handle)
        if claim is None:
            pending = self._ui_sessions.create_pending_claim(identity=registration.handle)
            return IdentityBootstrapStatus(
                identity=registration.handle,
                did=registration.did,
                registration_status="claim_required",
                claim_url=f"{self._server_base_url}/ui/claim/{pending.token}",
            )
        if claim.claim_status == ClaimStatus.ACCEPTED:
            return IdentityBootstrapStatus(
                identity=registration.handle,
                did=registration.did,
                registration_status="claimed",
                principal_id=claim.principal_id,
            )
        if claim.claim_status == ClaimStatus.REJECTED:
            return IdentityBootstrapStatus(
                identity=registration.handle,
                did=registration.did,
                registration_status="rejected",
                principal_id=claim.principal_id,
            )
        return IdentityBootstrapStatus(
            identity=registration.handle,
            did=registration.did,
            registration_status="pending",
            principal_id=claim.principal_id,
        )
