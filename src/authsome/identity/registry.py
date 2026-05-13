"""Server-owned identity registry."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from authsome.identity.keys import public_key_from_did_key, validate_handle


class IdentityRegistration(BaseModel):
    """Registered identity binding stored by the daemon."""

    handle: str
    did: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class IdentityRegistrationError(ValueError):
    """Raised when an identity registration conflicts with existing registry state."""


class IdentityRegistry:
    """JSON-backed authoritative registry for daemon identity handles."""

    def __init__(self, server_home: Path) -> None:
        self._path = server_home / "identity_registry.json"

    def register(self, *, handle: str, did: str) -> IdentityRegistration:
        """Register a handle/DID binding, idempotent only for the same pair."""
        handle = validate_handle(handle)
        public_key_from_did_key(did)

        entries = self._load()
        existing = entries.get(handle)
        if existing is not None:
            registration = IdentityRegistration.model_validate(existing)
            if registration.did == did:
                return registration
            raise IdentityRegistrationError(f"Identity handle '{handle}' is already registered")

        for registered_handle, raw in entries.items():
            registration = IdentityRegistration.model_validate(raw)
            if registration.did == did:
                raise IdentityRegistrationError(f"DID is already registered to identity handle '{registered_handle}'")

        now = datetime.now(UTC)
        registration = IdentityRegistration(handle=handle, did=did, created_at=now, updated_at=now)
        entries[handle] = registration.model_dump(mode="json")
        self._save(entries)
        return registration

    def resolve(self, handle: str) -> IdentityRegistration | None:
        entries = self._load()
        raw = entries.get(handle)
        if raw is None:
            return None
        return IdentityRegistration.model_validate(raw)

    def _load(self) -> dict[str, dict[str, object]]:
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        if not isinstance(data, dict):
            return {}
        return {str(key): value for key, value in data.items() if isinstance(value, dict)}

    def _save(self, entries: dict[str, dict[str, object]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(entries, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp_path, self._path)
