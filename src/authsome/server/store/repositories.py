"""Typed repositories for server-owned relational Store records."""

import asyncio
import builtins
import json
import threading
import uuid
from collections.abc import Sequence
from concurrent.futures import Future
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from loguru import logger
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, LogRecordExporter, LogRecordExportResult

from authsome.audit import AuditEvent
from authsome.auth.models.config import ServerConfig
from authsome.auth.models.provider import ProviderDefinition
from authsome.errors import ProviderAlreadyRegisteredError
from authsome.identity.helpers import public_key_from_did_key, validate_handle
from authsome.identity.principal import (
    ClaimStatus,
    IdentityClaimRecord,
    PrincipalRecord,
    PrincipalRole,
)
from authsome.identity.registry import IdentityRegistration
from authsome.server.schemas import GlobalProviderConnectionRecord, PrincipalVaultBindingRecord, VaultRecord
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


@dataclass(frozen=True)
class AuditEventInsert:
    """Audit event row prepared for Store persistence."""

    event_id: str
    timestamp: str
    event: str
    source: str
    principal_id: str | None
    identity: str | None
    provider: str | None
    connection: str | None
    payload: dict[str, Any]


class AuditEventRegistry:
    """Relational audit event registry."""

    def __init__(self, database: StoreDatabase) -> None:
        self._db = database

    async def insert_many(self, events: list[AuditEventInsert]) -> None:
        if not events:
            return
        now = _dump_dt(utc_now())
        for event in events:
            await self._db.execute(
                "INSERT INTO audit_events "
                "(event_id, timestamp, event, source, principal_id, identity, provider, connection, "
                "payload_json, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(event_id) DO NOTHING",
                [
                    event.event_id,
                    event.timestamp,
                    event.event,
                    event.source,
                    event.principal_id,
                    event.identity,
                    event.provider,
                    event.connection,
                    json.dumps(event.payload, separators=(",", ":"), sort_keys=True),
                    now,
                ],
            )

    async def list_recent(self, *, limit: int = 50, principal_id: str | None = None) -> list[dict[str, Any]]:
        bounded_limit = min(max(limit, 1), 500)
        if principal_id is None:
            rows = await self._db.fetch_all(
                "SELECT payload_json FROM audit_events ORDER BY timestamp DESC, event_id DESC LIMIT ?",
                [bounded_limit],
            )
        else:
            rows = await self._db.fetch_all(
                "SELECT payload_json FROM audit_events "
                "WHERE principal_id = ? "
                "ORDER BY timestamp DESC, event_id DESC LIMIT ?",
                [principal_id, bounded_limit],
            )
        return [json.loads(row["payload_json"]) for row in rows]

    def configure_exporter(self, loop: asyncio.AbstractEventLoop | None = None):
        """Configure the process OTel logger provider to export audit logs to Store."""
        global _audit_logger_provider  # noqa: PLW0603

        exporter = _StoreAuditExporter(self, loop or asyncio.get_running_loop())
        with _audit_provider_lock:
            if _audit_logger_provider is None:
                provider = LoggerProvider()
                provider.add_log_record_processor(BatchLogRecordProcessor(_delegating_audit_exporter))
                try:
                    set_logger_provider(provider)
                except Exception as exc:  # pragma: no cover - OTel guards against repeated global setup
                    logger.warning("Could not set OpenTelemetry logger provider: {}", exc)
                _audit_logger_provider = provider
            _delegating_audit_exporter.set_active(exporter)
            return ServerAuditLog(exporter, _audit_logger_provider, self)


class _StoreAuditExporter(LogRecordExporter):
    """Persist Authsome audit OTel log records through AuditEventRegistry."""

    def __init__(self, registry: AuditEventRegistry, loop: asyncio.AbstractEventLoop) -> None:
        self._registry = registry
        self._loop = loop
        self._lock = threading.Lock()
        self._futures: list[Future[None]] = []
        self._pending_rows: list[AuditEventInsert] = []
        self._closed = False

    def export(self, batch: Sequence[Any]) -> LogRecordExportResult:
        if self._closed:
            return LogRecordExportResult.FAILURE
        rows = _rows_from_batch(batch)
        if not rows:
            return LogRecordExportResult.SUCCESS
        try:
            if self._is_loop_thread():
                with self._lock:
                    self._pending_rows.extend(rows)
                return LogRecordExportResult.SUCCESS
            future = asyncio.run_coroutine_threadsafe(self._registry.insert_many(rows), self._loop)
            with self._lock:
                self._futures.append(future)
        except Exception as exc:
            logger.warning("Could not persist audit events: {}", exc)
            return LogRecordExportResult.FAILURE
        finally:
            self._drop_finished_futures()
        return LogRecordExportResult.SUCCESS

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        timeout_seconds = timeout_millis / 1000
        with self._lock:
            futures = list(self._futures)
        ok = True
        for future in futures:
            try:
                future.result(timeout=timeout_seconds)
            except Exception as exc:
                logger.warning("Could not flush audit event write: {}", exc)
                ok = False
        self._drop_finished_futures()
        return ok

    async def async_force_flush(self) -> None:
        pending = self._pop_pending_rows()
        if pending:
            await self._registry.insert_many(pending)
        with self._lock:
            futures = list(self._futures)
        for future in futures:
            await asyncio.wrap_future(future)
        self._drop_finished_futures()

    def shutdown(self) -> None:
        self._closed = True
        self.force_flush()

    def _is_loop_thread(self) -> bool:
        try:
            return asyncio.get_running_loop() is self._loop
        except RuntimeError:
            return False

    def _pop_pending_rows(self) -> list[AuditEventInsert]:
        with self._lock:
            rows = self._pending_rows
            self._pending_rows = []
        return rows

    def _drop_finished_futures(self) -> None:
        with self._lock:
            self._futures = [future for future in self._futures if not future.done()]


class _DelegatingAuditExporter(LogRecordExporter):
    """Stable global exporter that forwards to the current Store audit exporter."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active: _StoreAuditExporter | None = None

    def set_active(self, exporter: _StoreAuditExporter | None) -> None:
        with self._lock:
            self._active = exporter

    def export(self, batch: Sequence[Any]) -> LogRecordExportResult:
        with self._lock:
            exporter = self._active
        if exporter is None:
            return LogRecordExportResult.SUCCESS
        return exporter.export(batch)

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        with self._lock:
            exporter = self._active
        return True if exporter is None else exporter.force_flush(timeout_millis=timeout_millis)

    def shutdown(self) -> None:
        with self._lock:
            exporter = self._active
            self._active = None
        if exporter is not None:
            exporter.shutdown()


_delegating_audit_exporter = _DelegatingAuditExporter()
_audit_provider_lock = threading.Lock()
_audit_logger_provider: LoggerProvider | None = None


class ServerAuditLog:
    """Store registry handle for emitting and querying audit records."""

    def __init__(self, exporter: _StoreAuditExporter, provider: LoggerProvider, registry: AuditEventRegistry) -> None:
        self._exporter = exporter
        self._provider = provider
        self._registry = registry

    def force_flush(self) -> None:
        self._provider.force_flush()
        self._exporter.force_flush()

    async def async_force_flush(self) -> None:
        self._provider.force_flush()
        await self._exporter.async_force_flush()

    async def list_events(self, *, limit: int = 50, principal_id: str | None = None) -> list[dict[str, Any]]:
        await self.async_force_flush()
        return await self._registry.list_recent(limit=limit, principal_id=principal_id)

    def shutdown(self) -> None:
        self.force_flush()
        _delegating_audit_exporter.set_active(None)
        self._exporter.shutdown()


def _rows_from_batch(batch: Sequence[Any]) -> list[AuditEventInsert]:
    rows: list[AuditEventInsert] = []
    for item in batch:
        payload = _payload_from_log_record(item)
        try:
            event = AuditEvent.model_validate(payload)
        except ValueError as exc:
            logger.debug("Skipping non-Authsome OTel log record: {}", exc)
            continue
        normalized = event.model_dump(mode="json")
        stored_payload = _flatten_event_payload(normalized)
        rows.append(
            AuditEventInsert(
                event_id=event.event_id,
                timestamp=normalized["timestamp"],
                event=event.event,
                source=event.source,
                principal_id=event.principal_id,
                identity=event.identity,
                provider=event.provider,
                connection=event.connection,
                payload=stored_payload,
            )
        )
    return rows


def _payload_from_log_record(item: Any) -> dict[str, Any]:
    log_record = getattr(item, "log_record", item)
    attributes = dict(getattr(log_record, "attributes", None) or {})
    if "event" in attributes:
        return attributes

    event_name = getattr(log_record, "event_name", None) or getattr(log_record, "body", "audit_event")
    return AuditEvent(event=str(event_name), timestamp=utc_now()).model_dump(mode="json")


def _flatten_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    flattened = dict(payload)
    metadata = flattened.pop("metadata", {})
    if isinstance(metadata, dict):
        flattened.update(metadata)
    return flattened


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

    async def list_all(self) -> list[PrincipalRecord]:
        rows = await self._db.fetch_all("SELECT * FROM principals ORDER BY created_at, principal_id")
        return [self._record(row) for row in rows]

    async def create_by_email(self, email: str, *, password_hash: str | None = None) -> PrincipalRecord:
        normalized = email.strip().lower()
        if await self.get_by_email(normalized) is not None:
            if password_hash is None:
                raise ValueError(f"Principal '{normalized}' already exists")
            raise ValueError(f"Account '{normalized}' is already registered")
        now = utc_now()
        role = await self._role_for_new_principal()
        record = PrincipalRecord(
            principal_id=f"principal_{uuid.uuid4().hex[:12]}",
            email=normalized,
            role=role,
            password_hash=password_hash,
            created_at=now,
            updated_at=now,
        )
        await self._db.execute(
            "INSERT INTO principals (principal_id, email, password_hash, role, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [record.principal_id, record.email, record.password_hash, record.role.value, _dump_dt(now), _dump_dt(now)],
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
            role=PrincipalRole(row["role"]),
            password_hash=row["password_hash"],
            created_at=_dt(row["created_at"]),
            updated_at=_dt(row["updated_at"]),
        )

    async def _role_for_new_principal(self) -> PrincipalRole:
        existing = await self._db.fetch_one("SELECT principal_id FROM principals LIMIT 1")
        return PrincipalRole.ADMIN if existing is None else PrincipalRole.USER


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


class GlobalProviderConnectionRegistry:
    """Relational registry for global provider connection pointers."""

    def __init__(self, database: StoreDatabase) -> None:
        self._db = database

    async def get(self, provider: str) -> GlobalProviderConnectionRecord | None:
        row = await self._db.fetch_one("SELECT * FROM global_provider_connections WHERE provider = ?", [provider])
        return self._record(row) if row else None

    async def list_all(self) -> list[GlobalProviderConnectionRecord]:
        rows = await self._db.fetch_all("SELECT * FROM global_provider_connections ORDER BY provider")
        return [self._record(row) for row in rows]

    async def upsert(self, record: GlobalProviderConnectionRecord) -> GlobalProviderConnectionRecord:
        existing = await self.get(record.provider)
        updated_at = utc_now()
        created_at = existing.created_at if existing is not None else updated_at
        stored = record.model_copy(update={"created_at": created_at, "updated_at": updated_at})
        await self._db.execute(
            "INSERT INTO global_provider_connections "
            "(provider, owner_principal_id, owner_vault_id, connection_name, created_by_identity, created_at, "
            "updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(provider) DO UPDATE SET "
            "owner_principal_id = excluded.owner_principal_id, "
            "owner_vault_id = excluded.owner_vault_id, "
            "connection_name = excluded.connection_name, "
            "created_by_identity = excluded.created_by_identity, "
            "created_at = excluded.created_at, "
            "updated_at = excluded.updated_at",
            [
                stored.provider,
                stored.owner_principal_id,
                stored.owner_vault_id,
                stored.connection_name,
                stored.created_by_identity,
                _dump_dt(stored.created_at),
                _dump_dt(stored.updated_at),
            ],
        )
        return stored

    async def delete(self, provider: str) -> bool:
        existing = await self.get(provider)
        if existing is None:
            return False
        await self._db.execute("DELETE FROM global_provider_connections WHERE provider = ?", [provider])
        return True

    async def delete_if_target(
        self,
        provider: str,
        owner_vault_id: str,
        connection_name: str,
        *,
        updated_at: datetime | None = None,
    ) -> bool:
        sql = (
            "DELETE FROM global_provider_connections WHERE provider = ? AND owner_vault_id = ? AND connection_name = ?"
        )
        params: list[Any] = [provider, owner_vault_id, connection_name]
        if updated_at is not None:
            sql = f"{sql} AND updated_at = ?"
            params.append(_dump_dt(updated_at))
        deleted = await self._db.execute_rowcount(
            sql,
            params,
        )
        return deleted > 0

    @staticmethod
    def _record(row: dict[str, Any]) -> GlobalProviderConnectionRecord:
        return GlobalProviderConnectionRecord(
            provider=row["provider"],
            owner_principal_id=row["owner_principal_id"],
            owner_vault_id=row["owner_vault_id"],
            connection_name=row["connection_name"],
            created_by_identity=row["created_by_identity"],
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
    global_provider_connections: GlobalProviderConnectionRegistry
    server_config: ServerConfigRepository
    provider_definitions: ProviderDefinitionRepository
    audit_events: AuditEventRegistry

    @property
    def backend(self) -> StoreBackend:
        return self.database.backend

    async def is_healthy(self) -> bool:
        return await self.database.is_healthy()

    async def close(self) -> None:
        await self.database.close()
