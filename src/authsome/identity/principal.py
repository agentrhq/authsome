"""Domain models for principals, vaults, and ownership bindings.

These are pure data models shared across server, cli, and identity modules.
Filesystem-backed registry implementations live in server/registries.py.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from authsome.utils import utc_now


class ClaimStatus(StrEnum):
    """Lifecycle state of an Identity's claim to a Principal."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class PrincipalRecord(BaseModel):
    """Principal account record."""

    principal_id: str
    email: str
    password_hash: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class VaultRecord(BaseModel):
    """Vault record owned as a first-class resource."""

    vault_id: str
    handle: str = "default"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class IdentityClaimRecord(BaseModel):
    """Binding from identity to principal with lifecycle state."""

    identity_handle: str
    principal_id: str
    claim_status: ClaimStatus = ClaimStatus.PENDING
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PrincipalVaultBindingRecord(BaseModel):
    """Binding from principal to a vault."""

    principal_id: str
    vault_id: str
    is_default: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
