from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from authsome.identity.principal import PrincipalRole
from authsome.server.ownership import OwnershipResolver
from authsome.server.store import create_server_store
from authsome.server.store.database import StoreDatabaseConfig, open_store_database


@pytest.mark.asyncio
async def test_resolution_maps_accepted_claim_to_principal_default_vault(tmp_path: Path) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        principal = await store.principals.create_by_email("dev@example.com")
        vault = await store.vaults.create_default()
        await store.principal_vault_bindings.bind_default(principal.principal_id, vault.vault_id)
        await store.identity_claims.claim_identity("steady-wisely-boldly-0042", principal.principal_id)
        await store.identity_claims.accept_claim("steady-wisely-boldly-0042")

        resolver = OwnershipResolver(
            principals=store.principals,
            vaults=store.vaults,
            claims=store.identity_claims,
            bindings=store.principal_vault_bindings,
        )
        context = await resolver.resolve(identity="steady-wisely-boldly-0042")

        assert context.principal_id == principal.principal_id
        assert context.vault_id == vault.vault_id
        assert context.role == PrincipalRole.ADMIN
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_resolution_rejects_unclaimed_identity(tmp_path: Path) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        resolver = OwnershipResolver(
            principals=store.principals,
            vaults=store.vaults,
            claims=store.identity_claims,
            bindings=store.principal_vault_bindings,
        )
        with pytest.raises(ValueError):
            await resolver.resolve(identity="steady-wisely-boldly-0042")
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_principal_registry_assigns_first_principal_admin_then_users(tmp_path: Path) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        first = await store.principals.create_by_email("admin@example.com")
        second = await store.principals.create_by_email("user@example.com")

        assert first.role == PrincipalRole.ADMIN
        assert second.role == PrincipalRole.USER
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_principal_role_migration_promotes_earliest_existing_principal(tmp_path: Path) -> None:
    db_path = tmp_path / "server" / "authsome.db"
    db_path.parent.mkdir(parents=True)
    connection = await aiosqlite.connect(db_path)
    try:
        await connection.execute(
            "CREATE TABLE principals ("
            "principal_id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE, password_hash TEXT, "
            "created_at TEXT NOT NULL, updated_at TEXT NOT NULL"
            ")"
        )
        await connection.execute(
            "INSERT INTO principals (principal_id, email, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ["principal_first", "first@example.com", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"],
        )
        await connection.execute(
            "INSERT INTO principals (principal_id, email, created_at, updated_at) VALUES (?, ?, ?, ?)",
            ["principal_second", "second@example.com", "2026-01-02T00:00:00+00:00", "2026-01-02T00:00:00+00:00"],
        )
        await connection.commit()
    finally:
        await connection.close()

    database = await open_store_database(StoreDatabaseConfig(backend="sqlite", dsn=str(db_path), home=tmp_path))
    try:
        first = await database.fetch_one("SELECT role FROM principals WHERE principal_id = ?", ["principal_first"])
        second = await database.fetch_one("SELECT role FROM principals WHERE principal_id = ?", ["principal_second"])

        assert first == {"role": PrincipalRole.ADMIN.value}
        assert second == {"role": PrincipalRole.USER.value}
    finally:
        await database.close()
