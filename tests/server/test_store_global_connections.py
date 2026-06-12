from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from authsome.server.schemas import GlobalProviderConnectionRecord
from authsome.server.store import ServerStore, create_server_store
from authsome.server.store import repositories as store_repositories


async def _create_owner(store: ServerStore) -> tuple[str, str]:
    principal = await store.principals.create_by_email("admin@example.com")
    vault = await store.vaults.create_default()
    return principal.principal_id, vault.vault_id


@pytest.mark.asyncio
async def test_global_provider_connection_roundtrip(tmp_path: Path) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        principal_id, vault_id = await _create_owner(store)
        record = GlobalProviderConnectionRecord(
            provider="github",
            owner_principal_id=principal_id,
            owner_vault_id=vault_id,
            connection_name="default",
            created_by_identity="admin-ready-boldly-0001",
        )

        await store.global_provider_connections.upsert(record)

        loaded = await store.global_provider_connections.get("github")
        assert loaded is not None
        assert loaded.provider == "github"
        assert loaded.owner_principal_id == principal_id
        assert loaded.owner_vault_id == vault_id
        assert loaded.connection_name == "default"
        assert loaded.created_by_identity == "admin-ready-boldly-0001"

        listed = await store.global_provider_connections.list_all()
        assert [row.provider for row in listed] == ["github"]
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_global_provider_connection_upsert_replaces_provider_pointer(tmp_path: Path) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        first_principal_id, first_vault_id = await _create_owner(store)
        second_principal_id = (await store.principals.create_by_email("admin2@example.com")).principal_id
        second_vault_id = (await store.vaults.create_default()).vault_id
        await store.global_provider_connections.upsert(
            GlobalProviderConnectionRecord(
                provider="github",
                owner_principal_id=first_principal_id,
                owner_vault_id=first_vault_id,
                connection_name="default",
            )
        )
        await store.global_provider_connections.upsert(
            GlobalProviderConnectionRecord(
                provider="github",
                owner_principal_id=second_principal_id,
                owner_vault_id=second_vault_id,
                connection_name="team",
            )
        )

        loaded = await store.global_provider_connections.get("github")
        assert loaded is not None
        assert loaded.owner_principal_id == second_principal_id
        assert loaded.owner_vault_id == second_vault_id
        assert loaded.connection_name == "team"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_global_provider_connection_upsert_preserves_created_at_and_advances_updated_at(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        first_principal_id, first_vault_id = await _create_owner(store)
        second_principal_id = (await store.principals.create_by_email("admin2@example.com")).principal_id
        second_vault_id = (await store.vaults.create_default()).vault_id
        first_now = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)
        second_now = first_now + timedelta(minutes=5)
        caller_created_at = first_now - timedelta(days=30)

        monkeypatch.setattr(store_repositories, "utc_now", lambda: first_now)
        inserted = await store.global_provider_connections.upsert(
            GlobalProviderConnectionRecord(
                provider="github",
                owner_principal_id=first_principal_id,
                owner_vault_id=first_vault_id,
                connection_name="default",
                created_at=caller_created_at,
                updated_at=caller_created_at,
            )
        )

        monkeypatch.setattr(store_repositories, "utc_now", lambda: second_now)
        replaced = await store.global_provider_connections.upsert(
            GlobalProviderConnectionRecord(
                provider="github",
                owner_principal_id=second_principal_id,
                owner_vault_id=second_vault_id,
                connection_name="team",
            )
        )

        loaded = await store.global_provider_connections.get("github")
        assert loaded is not None
        assert inserted.created_at == first_now
        assert inserted.updated_at == first_now
        assert loaded.created_at == first_now
        assert replaced.created_at == first_now
        assert replaced.updated_at == second_now
        assert loaded.updated_at == second_now
        assert loaded.created_at != caller_created_at
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_global_provider_connection_delete(tmp_path: Path) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        principal_id, vault_id = await _create_owner(store)
        await store.global_provider_connections.upsert(
            GlobalProviderConnectionRecord(
                provider="github",
                owner_principal_id=principal_id,
                owner_vault_id=vault_id,
                connection_name="default",
            )
        )

        deleted = await store.global_provider_connections.delete("github")

        assert deleted is True
        assert await store.global_provider_connections.get("github") is None
        assert await store.global_provider_connections.delete("github") is False
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_global_provider_connection_delete_if_target_removes_matching_pointer(tmp_path: Path) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        principal_id, vault_id = await _create_owner(store)
        await store.global_provider_connections.upsert(
            GlobalProviderConnectionRecord(
                provider="github",
                owner_principal_id=principal_id,
                owner_vault_id=vault_id,
                connection_name="default",
            )
        )

        deleted = await store.global_provider_connections.delete_if_target("github", vault_id, "default")

        assert deleted is True
        assert await store.global_provider_connections.get("github") is None
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_global_provider_connection_delete_if_target_ignores_non_matching_pointer(tmp_path: Path) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        principal_id, vault_id = await _create_owner(store)
        await store.global_provider_connections.upsert(
            GlobalProviderConnectionRecord(
                provider="github",
                owner_principal_id=principal_id,
                owner_vault_id=vault_id,
                connection_name="default",
            )
        )

        deleted = await store.global_provider_connections.delete_if_target("github", vault_id, "team")

        assert deleted is False
        loaded = await store.global_provider_connections.get("github")
        assert loaded is not None
        assert loaded.connection_name == "default"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_global_provider_connection_delete_if_target_does_not_remove_repointed_pointer(tmp_path: Path) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        first_principal_id, first_vault_id = await _create_owner(store)
        second_principal_id = (await store.principals.create_by_email("admin2@example.com")).principal_id
        second_vault_id = (await store.vaults.create_default()).vault_id
        await store.global_provider_connections.upsert(
            GlobalProviderConnectionRecord(
                provider="github",
                owner_principal_id=first_principal_id,
                owner_vault_id=first_vault_id,
                connection_name="default",
            )
        )
        await store.global_provider_connections.upsert(
            GlobalProviderConnectionRecord(
                provider="github",
                owner_principal_id=second_principal_id,
                owner_vault_id=second_vault_id,
                connection_name="team",
            )
        )

        deleted = await store.global_provider_connections.delete_if_target("github", first_vault_id, "default")

        assert deleted is False
        loaded = await store.global_provider_connections.get("github")
        assert loaded is not None
        assert loaded.owner_principal_id == second_principal_id
        assert loaded.owner_vault_id == second_vault_id
        assert loaded.connection_name == "team"
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_global_provider_connection_delete_if_target_respects_observed_updated_at(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        principal_id, vault_id = await _create_owner(store)
        first_now = datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC)
        second_now = first_now + timedelta(minutes=5)

        monkeypatch.setattr(store_repositories, "utc_now", lambda: first_now)
        observed = await store.global_provider_connections.upsert(
            GlobalProviderConnectionRecord(
                provider="github",
                owner_principal_id=principal_id,
                owner_vault_id=vault_id,
                connection_name="default",
            )
        )

        monkeypatch.setattr(store_repositories, "utc_now", lambda: second_now)
        await store.global_provider_connections.upsert(
            GlobalProviderConnectionRecord(
                provider="github",
                owner_principal_id=principal_id,
                owner_vault_id=vault_id,
                connection_name="default",
            )
        )

        deleted = await store.global_provider_connections.delete_if_target(
            "github",
            vault_id,
            "default",
            updated_at=observed.updated_at,
        )

        assert deleted is False
        loaded = await store.global_provider_connections.get("github")
        assert loaded is not None
        assert loaded.owner_vault_id == vault_id
        assert loaded.connection_name == "default"
        assert loaded.updated_at == second_now
    finally:
        await store.close()
