"""Relational server Store database wiring."""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import aiosqlite

from authsome.server.config import get_server_config

StoreBackend = Literal["sqlite", "postgres"]


@dataclass(frozen=True)
class StoreDatabaseConfig:
    """Resolved relational Store backend configuration."""

    backend: StoreBackend
    dsn: str
    home: Path


class StoreDatabase:
    """Small async database adapter shared by Store repositories."""

    def __init__(self, *, config: StoreDatabaseConfig, connection: Any) -> None:
        self.config = config
        self._connection = connection

    @property
    def backend(self) -> StoreBackend:
        return self.config.backend

    def _sql(self, sql: str) -> str:
        if self.backend != "postgres":
            return sql
        index = 0
        parts: list[str] = []
        for char in sql:
            if char == "?":
                index += 1
                parts.append(f"${index}")
            else:
                parts.append(char)
        return "".join(parts)

    async def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        if self.backend == "sqlite":
            cursor = await self._connection.execute(sql, params)
            row = await cursor.fetchone()
            await cursor.close()
            return dict(row) if row is not None else None
        row = await self._connection.fetchrow(self._sql(sql), *params)
        return dict(row) if row is not None else None

    async def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        if self.backend == "sqlite":
            cursor = await self._connection.execute(sql, params)
            rows = await cursor.fetchall()
            await cursor.close()
            return [dict(row) for row in rows]
        rows = await self._connection.fetch(self._sql(sql), *params)
        return [dict(row) for row in rows]

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        if self.backend == "sqlite":
            await self._connection.execute(sql, params)
            await self._connection.commit()
            return
        await self._connection.execute(self._sql(sql), *params)

    async def execute_many(self, statements: Sequence[str]) -> None:
        for statement in statements:
            await self.execute(statement)

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        if self.backend == "sqlite":
            await self._connection.execute("BEGIN")
            try:
                yield
            except Exception:
                await self._connection.rollback()
                raise
            else:
                await self._connection.commit()
            return
        async with self._connection.transaction():
            yield

    async def is_healthy(self) -> bool:
        try:
            row = await self.fetch_one("SELECT 1 AS ok")
            return row == {"ok": 1}
        except Exception:
            return False

    async def close(self) -> None:
        await self._connection.close()


def resolve_store_database_config(home: Path | None = None, database_url: str | None = None) -> StoreDatabaseConfig:
    """Resolve the relational Store backend from explicit config or defaults."""
    server_config = get_server_config(home)
    resolved_home = server_config.home
    raw_url = database_url if database_url is not None else server_config.database
    parsed = urlparse(raw_url)
    if not parsed.scheme:
        return StoreDatabaseConfig(backend="sqlite", dsn=raw_url, home=resolved_home)
    if parsed.scheme in {"postgres", "postgresql"}:
        return StoreDatabaseConfig(backend="postgres", dsn=raw_url, home=resolved_home)
    if parsed.scheme == "sqlite":
        if parsed.path in {"", "/"}:
            raise ValueError("sqlite AUTHSOME_DATABASE_URL must include a database path")
        return StoreDatabaseConfig(backend="sqlite", dsn=str(parsed.path), home=resolved_home)
    raise ValueError(f"Unsupported AUTHSOME_DATABASE_URL scheme: {parsed.scheme}")


async def open_store_database(config: StoreDatabaseConfig) -> StoreDatabase:
    """Open the configured Store database and initialize its schema."""
    if config.backend == "sqlite":
        db_path = Path(config.dsn)
        db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = await aiosqlite.connect(db_path)
    connection.row_factory = aiosqlite.Row
    await connection.execute("PRAGMA foreign_keys = ON")
    await connection.commit()
    database = StoreDatabase(config=config, connection=connection)
    await initialize_schema(database)
    return database

    try:
        import asyncpg  # noqa: PLC0415
    except ImportError as exc:
        raise RuntimeError("Postgres Store requires installing authsome[postgres]") from exc

    connection = await asyncpg.connect(config.dsn)
    database = StoreDatabase(config=config, connection=connection)
    await initialize_schema(database)
    return database


def build_schema(backend: StoreBackend) -> list[str]:
    """Build schema statements with only the dialect-specific fragments varied."""
    if backend == "postgres":
        default_bool = "BOOLEAN NOT NULL DEFAULT FALSE"
        true_predicate = "TRUE"
    else:
        default_bool = "INTEGER NOT NULL DEFAULT 0"
        true_predicate = "1"

    return [
        "CREATE TABLE IF NOT EXISTS store_schema_version (version INTEGER PRIMARY KEY)",
        "INSERT INTO store_schema_version (version) SELECT 1 "
        "WHERE NOT EXISTS (SELECT 1 FROM store_schema_version WHERE version = 1)",
        "CREATE TABLE IF NOT EXISTS identity_registrations ("
        "handle TEXT PRIMARY KEY, did TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, updated_at TEXT NOT NULL"
        ")",
        "CREATE TABLE IF NOT EXISTS principals ("
        "principal_id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, password_hash TEXT, "
        "role TEXT NOT NULL DEFAULT 'user', created_at TEXT NOT NULL, updated_at TEXT NOT NULL"
        ")",
        "CREATE TABLE IF NOT EXISTS vaults ("
        "vault_id TEXT PRIMARY KEY, handle TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL"
        ")",
        "CREATE TABLE IF NOT EXISTS identity_claims ("
        "identity_handle TEXT PRIMARY KEY, "
        "principal_id TEXT NOT NULL REFERENCES principals(principal_id) ON DELETE CASCADE, "
        "claim_status TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL"
        ")",
        "CREATE TABLE IF NOT EXISTS principal_vault_bindings ("
        "principal_id TEXT NOT NULL REFERENCES principals(principal_id) ON DELETE CASCADE, "
        "vault_id TEXT NOT NULL REFERENCES vaults(vault_id) ON DELETE CASCADE, "
        f"is_default {default_bool}, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, "
        "PRIMARY KEY (principal_id, vault_id)"
        ")",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_principal_vault_default "
        f"ON principal_vault_bindings(principal_id) WHERE is_default = {true_predicate}",
        "CREATE TABLE IF NOT EXISTS server_config ("
        "config_key TEXT PRIMARY KEY, config_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL"
        ")",
        "CREATE TABLE IF NOT EXISTS custom_provider_definitions ("
        "name TEXT PRIMARY KEY, definition_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL"
        ")",
        "CREATE TABLE IF NOT EXISTS audit_events ("
        "event_id TEXT PRIMARY KEY, "
        "timestamp TEXT NOT NULL, "
        "event TEXT NOT NULL, "
        "source TEXT NOT NULL, "
        "principal_id TEXT, "
        "identity TEXT, "
        "provider TEXT, "
        "connection TEXT, "
        "payload_json TEXT NOT NULL, "
        "created_at TEXT NOT NULL"
        ")",
        "CREATE INDEX IF NOT EXISTS idx_audit_events_timestamp ON audit_events(timestamp DESC, event_id DESC)",
        "CREATE INDEX IF NOT EXISTS idx_audit_events_principal ON audit_events(principal_id)",
    ]


async def initialize_schema(database: StoreDatabase) -> None:
    await database.execute_many(build_schema(database.backend))


async def create_server_store(home: Path | None = None, database_url: str | None = None):
    """Create the server-owned relational Store."""
    from authsome.server.store.repositories import (  # noqa: PLC0415
        AuditEventRegistry,
        IdentityClaimRegistry,
        IdentityRegistry,
        PrincipalRegistry,
        PrincipalVaultBindingRegistry,
        ProviderDefinitionRepository,
        ServerConfigRepository,
        ServerStore,
        VaultRegistry,
    )

    config = resolve_store_database_config(home=home, database_url=database_url)
    database = await open_store_database(config)
    return ServerStore(
        database=database,
        home=config.home,
        identity_registry=IdentityRegistry(database),
        principals=PrincipalRegistry(database),
        vaults=VaultRegistry(database),
        identity_claims=IdentityClaimRegistry(database),
        principal_vault_bindings=PrincipalVaultBindingRegistry(database),
        server_config=ServerConfigRepository(database),
        provider_definitions=ProviderDefinitionRepository(database),
        audit_events=AuditEventRegistry(database),
    )
