"""Server-owned identity registry."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from authsome.identity.local import public_key_from_did_key, validate_handle


class IdentityRegistration(BaseModel):
    """Registered identity binding stored by the daemon."""

    handle: str
    did: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class IdentityRegistrationError(ValueError):
    """Raised when an identity registration conflicts with existing registry state."""


class IdentityRegistry:
    """Filesystem-backed authoritative registry for daemon identity handles."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def _load_all(self) -> list[IdentityRegistration]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        if not isinstance(raw, list):
            return []
        registrations: list[IdentityRegistration] = []
        for item in raw:
            try:
                registrations.append(IdentityRegistration.model_validate(item))
            except Exception:
                continue
        return registrations

    def _save_all(self, registrations: list[IdentityRegistration]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps([registration.model_dump(mode="json") for registration in registrations], indent=2),
            encoding="utf-8",
        )

    async def register(self, *, handle: str, did: str) -> IdentityRegistration:
        """Register a handle/DID binding, idempotent only for the same pair."""
        handle = validate_handle(handle)
        public_key_from_did_key(did)

        registrations = self._load_all()

        existing = next((registration for registration in registrations if registration.handle == handle), None)
        if existing is not None:
            if existing.did == did:
                return existing
            raise IdentityRegistrationError(f"Identity handle '{handle}' is already registered")

        for registration in registrations:
            if registration.did == did:
                raise IdentityRegistrationError(f"DID is already registered to identity handle '{registration.handle}'")

        now = datetime.now(UTC)
        registration = IdentityRegistration(handle=handle, did=did, created_at=now, updated_at=now)
        registrations.append(registration)
        self._save_all(registrations)
        return registration

    async def resolve(self, handle: str) -> IdentityRegistration | None:
        for registration in self._load_all():
            if registration.handle == handle:
                return registration
        return None

    async def list_handles(self) -> list[str]:
        """Return all registered identity handles."""
        registrations = self._load_all()
        return sorted(registration.handle for registration in registrations)
