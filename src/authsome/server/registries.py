"""Server-owned filesystem-backed registries.

All state under ~/.authsome/server/ is owned here.
Domain models (IdentityRegistration, PrincipalRecord, etc.) live in
identity/ and are imported freely; only the persistence implementations
belong in this module.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel

from authsome.identity.local import public_key_from_did_key, validate_handle
from authsome.identity.principal import (
    ClaimStatus,
    IdentityClaimRecord,
    PrincipalRecord,
    PrincipalVaultBindingRecord,
    VaultRecord,
)
from authsome.identity.registry import IdentityRegistration
from authsome.utils import utc_now


class _JsonRegistry[T: BaseModel]:
    """Simple JSON-list persistence helper."""

    def __init__(self, path: Path, model_type: type[T]) -> None:
        self._path = path
        self._model_type = model_type

    def _load_all(self) -> list[T]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        if not isinstance(raw, list):
            return []
        items: list[T] = []
        for item in raw:
            try:
                items.append(self._model_type.model_validate(item))
            except Exception:
                continue
        return items

    def _save_all(self, records: list[T]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps([r.model_dump(mode="json") for r in records], indent=2),
            encoding="utf-8",
        )


class IdentityRegistrationError(ValueError):
    """Raised when an identity registration conflicts with existing registry state."""


class IdentityRegistry(_JsonRegistry[IdentityRegistration]):
    """Filesystem-backed authoritative registry for daemon identity handles."""

    def __init__(self, path: Path) -> None:
        super().__init__(path, IdentityRegistration)

    async def register(self, *, handle: str, did: str) -> IdentityRegistration:
        """Register a handle/DID binding, idempotent only for the same pair."""
        handle = validate_handle(handle)
        public_key_from_did_key(did)

        registrations = self._load_all()

        existing = next((r for r in registrations if r.handle == handle), None)
        if existing is not None:
            if existing.did == did:
                return existing
            raise IdentityRegistrationError(f"Identity handle '{handle}' is already registered")

        for r in registrations:
            if r.did == did:
                raise IdentityRegistrationError(f"DID is already registered to identity handle '{r.handle}'")

        now = datetime.now(UTC)
        registration = IdentityRegistration(handle=handle, did=did, created_at=now, updated_at=now)
        registrations.append(registration)
        self._save_all(registrations)
        return registration

    async def resolve(self, handle: str) -> IdentityRegistration | None:
        for r in self._load_all():
            if r.handle == handle:
                return r
        return None

    async def list_handles(self) -> list[str]:
        return sorted(r.handle for r in self._load_all())


class PrincipalRegistry(_JsonRegistry[PrincipalRecord]):
    """Filesystem-backed principal registry."""

    def __init__(self, path: Path) -> None:
        super().__init__(path, PrincipalRecord)

    async def get(self, principal_id: str) -> PrincipalRecord | None:
        return next((r for r in self._load_all() if r.principal_id == principal_id), None)

    async def get_by_email(self, email: str) -> PrincipalRecord | None:
        normalized = email.strip().lower()
        return next((r for r in self._load_all() if r.email == normalized), None)

    async def get_or_create_by_email(self, email: str) -> PrincipalRecord:
        normalized = email.strip().lower()
        existing = await self.get_by_email(normalized)
        if existing is not None:
            return existing
        now = utc_now()
        record = PrincipalRecord(
            principal_id=f"principal_{uuid.uuid4().hex[:12]}",
            email=normalized,
            created_at=now,
            updated_at=now,
        )
        records = self._load_all()
        records.append(record)
        self._save_all(records)
        return record


class VaultRegistry(_JsonRegistry[VaultRecord]):
    """Filesystem-backed vault registry."""

    def __init__(self, path: Path) -> None:
        super().__init__(path, VaultRecord)

    async def get(self, vault_id: str) -> VaultRecord | None:
        return next((r for r in self._load_all() if r.vault_id == vault_id), None)

    async def list_all(self) -> list[VaultRecord]:
        return self._load_all()

    async def create_default(self) -> VaultRecord:
        now = utc_now()
        record = VaultRecord(
            vault_id=f"vault_{uuid.uuid4().hex[:12]}",
            handle="default",
            created_at=now,
            updated_at=now,
        )
        records = self._load_all()
        records.append(record)
        self._save_all(records)
        return record


class IdentityClaimRegistry(_JsonRegistry[IdentityClaimRecord]):
    """Filesystem-backed identity-claim registry."""

    def __init__(self, path: Path) -> None:
        super().__init__(path, IdentityClaimRecord)

    async def resolve(self, identity_handle: str) -> IdentityClaimRecord | None:
        return next((r for r in self._load_all() if r.identity_handle == identity_handle), None)

    async def require_claim(self, identity_handle: str) -> IdentityClaimRecord:
        claim = await self.resolve(identity_handle)
        if claim is None:
            raise ValueError(f"Identity '{identity_handle}' is not claimed")
        return claim

    async def claim_identity(self, identity_handle: str, principal_id: str) -> IdentityClaimRecord:
        existing = await self.resolve(identity_handle)
        if existing is not None:
            if existing.principal_id != principal_id:
                raise ValueError(f"Identity '{identity_handle}' is already claimed")
            return existing
        now = utc_now()
        record = IdentityClaimRecord(
            identity_handle=identity_handle,
            principal_id=principal_id,
            claim_status=ClaimStatus.PENDING,
            created_at=now,
            updated_at=now,
        )
        records = self._load_all()
        records.append(record)
        self._save_all(records)
        return record

    async def accept_claim(self, identity_handle: str) -> IdentityClaimRecord:
        return await self._set_status(identity_handle, ClaimStatus.ACCEPTED)

    async def reject_claim(self, identity_handle: str) -> IdentityClaimRecord:
        return await self._set_status(identity_handle, ClaimStatus.REJECTED)

    async def _set_status(self, identity_handle: str, status: ClaimStatus) -> IdentityClaimRecord:
        records = self._load_all()
        for i, record in enumerate(records):
            if record.identity_handle == identity_handle:
                records[i] = record.model_copy(update={"claim_status": status, "updated_at": utc_now()})
                self._save_all(records)
                return records[i]
        raise ValueError(f"No claim found for identity '{identity_handle}'")


class PrincipalVaultBindingRegistry(_JsonRegistry[PrincipalVaultBindingRecord]):
    """Filesystem-backed principal-vault binding registry."""

    def __init__(self, path: Path) -> None:
        super().__init__(path, PrincipalVaultBindingRecord)

    async def list_for_principal(self, principal_id: str) -> list[PrincipalVaultBindingRecord]:
        return [r for r in self._load_all() if r.principal_id == principal_id]

    async def get_default_vault(self, principal_id: str) -> PrincipalVaultBindingRecord | None:
        return next(
            (r for r in self._load_all() if r.principal_id == principal_id and r.is_default),
            None,
        )

    async def require_default_vault(self, principal_id: str) -> PrincipalVaultBindingRecord:
        binding = await self.get_default_vault(principal_id)
        if binding is None:
            raise ValueError(f"Principal '{principal_id}' has no default vault")
        return binding

    async def bind_default(self, principal_id: str, vault_id: str) -> PrincipalVaultBindingRecord:
        existing = await self.get_default_vault(principal_id)
        if existing is not None:
            if existing.vault_id == vault_id:
                return existing
            raise ValueError(f"Principal '{principal_id}' already has a default vault")
        now = utc_now()
        record = PrincipalVaultBindingRecord(
            principal_id=principal_id,
            vault_id=vault_id,
            is_default=True,
            created_at=now,
            updated_at=now,
        )
        records = self._load_all()
        records.append(record)
        self._save_all(records)
        return record
