"""Typed repositories for server-owned relational Store records."""

from __future__ import annotations

import builtins
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from authsome.auth.models.config import ServerConfig
from authsome.auth.models.provider import ProviderDefinition
from authsome.errors import ProviderAlreadyRegisteredError
from authsome.identity.local import public_key_from_did_key, validate_handle
from authsome.identity.principal import (
    ClaimStatus,
    IdentityClaimRecord,
    PrincipalRecord,
    PrincipalVaultBindingRecord,
    VaultRecord,
)
from authsome.identity.registry import IdentityRegistration
from authsome.server.store.database import StoreBackend, StoreDatabase
from authsome.utils import utc_now


class IdentityRegistrationError(ValueError):
    """Raised when an identity registration conflicts with existing registry state."""


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _dump_dt(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _bool(value: Any) -> bool:
    return bool(value)


class IdentityRegistry:
    """Relational authoritative registry for daemon identity handles."""

    def __init__(self, database: StoreDatabase) -> None:
        self._db = database

    async def register(self, *, handle: str, did: str) -> IdentityRegistration:
        """Register a handle/DID binding, idempotent only for the same pair."""
        handle = validate_handle(handle)
        public_key_from_did_key(did)

        existing = await self.resolve(handle)
        if existing is not None:
            if existing.did == did:
                return existing
            raise IdentityRegistrationError(f"Identity handle '{handle}' is already registered")

        did_row = await self._db.fetch_one("SELECT handle FROM identity_registrations WHERE did = ?", [did])
        if did_row is not None:
            raise IdentityRegistrationError(f"DID is already registered to identity handle '{did_row['handle']}'")

        now = utc_now()
        await self._db.execute(
            "INSERT INTO identity_registrations (handle, did, created_at, updated_at) VALUES (?, ?, ?, ?)",
            [handle, did, _dump_dt(now), _dump_dt(now)],
        )
        return IdentityRegistration(handle=handle, did=did, created_at=now, updated_at=now)

    async def resolve(self, handle: str) -> IdentityRegistration | None:
        row = await self._db.fetch_one("SELECT * FROM identity_registrations WHERE handle = ?", [handle])
        if row is None:
            return None
        return IdentityRegistration(
            handle=row["handle"],
            did=row["did"],
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )

    async def list_handles(self) -> list[str]:
        rows = await self._db.fetch_all("SELECT handle FROM identity_registrations ORDER BY handle")
        return [row["handle"] for row in rows]


class PrincipalRegistry:
    """Relational principal registry."""

    def __init__(self, database: StoreDatabase) -> None:
        self._db = database

    async def get(self, principal_id: str) -> PrincipalRecord | None:
        row = await self._db.fetch_one("SELECT * FROM principals WHERE principal_id = ?", [principal_id])
        return self._record(row) if row else None

    async def get_by_email(self, email: str) -> PrincipalRecord | None:
        normalized = email.strip().lower()
        row = await self._db.fetch_one("SELECT * FROM principals WHERE email = ?", [normalized])
        return self._record(row) if row else None

    async def create_by_email(self, email: str, *, password_hash: str | None = None) -> PrincipalRecord:
        normalized = email.strip().lower()
        if await self.get_by_email(normalized) is not None:
            if password_hash is None:
                raise ValueError(f"Principal '{normalized}' already exists")
            raise ValueError(f"Hosted account '{normalized}' is already registered")
        now = utc_now()
        record = PrincipalRecord(
            principal_id=f"principal_{uuid.uuid4().hex[:12]}",
            email=normalized,
            password_hash=password_hash,
            created_at=now,
            updated_at=now,
        )
        await self._db.execute(
            "INSERT INTO principals (principal_id, email, password_hash, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            [record.principal_id, record.email, record.password_hash, _dump_dt(now), _dump_dt(now)],
        )
        return record

    async def update_password(self, principal_id: str, *, password_hash: str) -> PrincipalRecord:
        existing = await self.get(principal_id)
        if existing is None:
            raise ValueError(f"Principal '{principal_id}' not found")
        updated = existing.model_copy(update={"password_hash": password_hash, "updated_at": utc_now()})
        await self._db.execute(
            "UPDATE principals SET password_hash = ?, updated_at = ? WHERE principal_id = ?",
            [updated.password_hash, _dump_dt(updated.updated_at), principal_id],
        )
        return updated

    @staticmethod
    def _record(row: dict[str, Any]) -> PrincipalRecord:
        return PrincipalRecord(
            principal_id=row["principal_id"],
            email=row["email"],
            password_hash=row["password_hash"],
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )


class VaultRegistry:
    """Relational vault registry."""

    def __init__(self, database: StoreDatabase) -> None:
        self._db = database

    async def get(self, vault_id: str) -> VaultRecord | None:
        row = await self._db.fetch_one("SELECT * FROM vaults WHERE vault_id = ?", [vault_id])
        return self._record(row) if row else None

    async def list_all(self) -> list[VaultRecord]:
        rows = await self._db.fetch_all("SELECT * FROM vaults ORDER BY created_at, vault_id")
        return [self._record(row) for row in rows]

    async def create_default(self) -> VaultRecord:
        now = utc_now()
        record = VaultRecord(
            vault_id=f"vault_{uuid.uuid4().hex[:12]}",
            handle="default",
            created_at=now,
            updated_at=now,
        )
        await self._db.execute(
            "INSERT INTO vaults (vault_id, handle, created_at, updated_at) VALUES (?, ?, ?, ?)",
            [record.vault_id, record.handle, _dump_dt(now), _dump_dt(now)],
        )
        return record

    @staticmethod
    def _record(row: dict[str, Any]) -> VaultRecord:
        return VaultRecord(
            vault_id=row["vault_id"],
            handle=row["handle"],
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )


class IdentityClaimRegistry:
    """Relational identity-claim registry."""

    def __init__(self, database: StoreDatabase) -> None:
        self._db = database

    async def resolve(self, identity_handle: str) -> IdentityClaimRecord | None:
        row = await self._db.fetch_one("SELECT * FROM identity_claims WHERE identity_handle = ?", [identity_handle])
        return self._record(row) if row else None

    async def list_for_principal(self, principal_id: str) -> list[IdentityClaimRecord]:
        rows = await self._db.fetch_all(
            "SELECT * FROM identity_claims WHERE principal_id = ? AND claim_status = ? ORDER BY identity_handle",
            [principal_id, ClaimStatus.ACCEPTED.value],
        )
        return [self._record(row) for row in rows]

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
        await self._db.execute(
            "INSERT INTO identity_claims "
            "(identity_handle, principal_id, claim_status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            [
                record.identity_handle,
                record.principal_id,
                record.claim_status.value,
                _dump_dt(now),
                _dump_dt(now),
            ],
        )
        return record

    async def accept_claim(self, identity_handle: str) -> IdentityClaimRecord:
        return await self._set_status(identity_handle, ClaimStatus.ACCEPTED)

    async def reject_claim(self, identity_handle: str) -> IdentityClaimRecord:
        return await self._set_status(identity_handle, ClaimStatus.REJECTED)

    async def _set_status(self, identity_handle: str, status: ClaimStatus) -> IdentityClaimRecord:
        existing = await self.resolve(identity_handle)
        if existing is None:
            raise ValueError(f"No claim found for identity '{identity_handle}'")
        updated = existing.model_copy(update={"claim_status": status, "updated_at": utc_now()})
        await self._db.execute(
            "UPDATE identity_claims SET claim_status = ?, updated_at = ? WHERE identity_handle = ?",
            [status.value, _dump_dt(updated.updated_at), identity_handle],
        )
        return updated

    @staticmethod
    def _record(row: dict[str, Any]) -> IdentityClaimRecord:
        return IdentityClaimRecord(
            identity_handle=row["identity_handle"],
            principal_id=row["principal_id"],
            claim_status=ClaimStatus(row["claim_status"]),
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )


class PrincipalVaultBindingRegistry:
    """Relational principal-vault binding registry."""

    def __init__(self, database: StoreDatabase) -> None:
        self._db = database

    async def list_for_principal(self, principal_id: str) -> list[PrincipalVaultBindingRecord]:
        rows = await self._db.fetch_all(
            "SELECT * FROM principal_vault_bindings WHERE principal_id = ? ORDER BY created_at, vault_id",
            [principal_id],
        )
        return [self._record(row) for row in rows]

    async def get_default_vault(self, principal_id: str) -> PrincipalVaultBindingRecord | None:
        row = await self._db.fetch_one(
            "SELECT * FROM principal_vault_bindings WHERE principal_id = ? AND is_default = ?",
            [principal_id, True],
        )
        return self._record(row) if row else None

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
        await self._db.execute(
            "INSERT INTO principal_vault_bindings "
            "(principal_id, vault_id, is_default, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            [record.principal_id, record.vault_id, record.is_default, _dump_dt(now), _dump_dt(now)],
        )
        return record

    @staticmethod
    def _record(row: dict[str, Any]) -> PrincipalVaultBindingRecord:
        return PrincipalVaultBindingRecord(
            principal_id=row["principal_id"],
            vault_id=row["vault_id"],
            is_default=_bool(row["is_default"]),
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )


class ServerConfigRepository:
    """Relational server config repository."""

    def __init__(self, database: StoreDatabase) -> None:
        self._db = database

    async def load(self) -> ServerConfig:
        row = await self._db.fetch_one("SELECT config_json FROM server_config WHERE config_key = ?", ["global"])
        if row is None:
            config = ServerConfig()
            await self.save(config)
            return config
        return ServerConfig.model_validate_json(row["config_json"])

    async def save(self, config: ServerConfig) -> None:
        now = _dump_dt(utc_now())
        await self._db.execute(
            "INSERT INTO server_config (config_key, config_json, created_at, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(config_key) DO UPDATE SET config_json = excluded.config_json, "
            "updated_at = excluded.updated_at",
            ["global", config.model_dump_json(), now, now],
        )


class ProviderDefinitionRepository:
    """Relational repository for custom provider definitions."""

    def __init__(self, database: StoreDatabase) -> None:
        self._db = database

    async def get(self, name: str) -> ProviderDefinition | None:
        row = await self._db.fetch_one("SELECT definition_json FROM custom_provider_definitions WHERE name = ?", [name])
        return ProviderDefinition.model_validate_json(row["definition_json"]) if row else None

    async def list(self) -> builtins.list[ProviderDefinition]:
        rows = await self._db.fetch_all("SELECT definition_json FROM custom_provider_definitions ORDER BY name")
        return [ProviderDefinition.model_validate_json(row["definition_json"]) for row in rows]

    async def save(self, definition: ProviderDefinition, *, force: bool = False) -> None:
        existing = await self.get(definition.name)
        if existing is not None and not force:
            raise ProviderAlreadyRegisteredError(definition.name)
        now = _dump_dt(utc_now())
        await self._db.execute(
            "INSERT INTO custom_provider_definitions (name, definition_json, created_at, updated_at) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET definition_json = excluded.definition_json, "
            "updated_at = excluded.updated_at",
            [definition.name, definition.model_dump_json(indent=2, exclude_none=True), now, now],
        )

    async def delete(self, name: str) -> bool:
        existing = await self.get(name)
        if existing is None:
            return False
        await self._db.execute("DELETE FROM custom_provider_definitions WHERE name = ?", [name])
        return True


@dataclass
class ServerStore:
    """Composition root for server Store repositories."""

    database: StoreDatabase
    home: Path
    identity_registry: IdentityRegistry
    principals: PrincipalRegistry
    vaults: VaultRegistry
    identity_claims: IdentityClaimRegistry
    principal_vault_bindings: PrincipalVaultBindingRegistry
    server_config: ServerConfigRepository
    provider_definitions: ProviderDefinitionRepository

    @property
    def backend(self) -> StoreBackend:
        return self.database.backend

    async def is_healthy(self) -> bool:
        return await self.database.is_healthy()

    async def close(self) -> None:
        await self.database.close()
