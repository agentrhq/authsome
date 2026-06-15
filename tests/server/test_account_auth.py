from pathlib import Path

import jwt
import pytest

from authsome.server.account_auth import UI_TOKEN_AUDIENCE, AccountAuthService
from authsome.server.store import ServerStore, create_server_store
from authsome.server.ui_sessions import UiSessionStore


async def _service(tmp_path: Path) -> tuple[AccountAuthService, ServerStore]:
    store = await create_server_store(home=tmp_path)
    return (
        AccountAuthService(
            principals=store.principals,
            vaults=store.vaults,
            bindings=store.principal_vault_bindings,
            sessions=UiSessionStore("test-secret"),
        ),
        store,
    )


async def _close(store: ServerStore) -> None:
    await store.close()


@pytest.mark.asyncio
async def test_register_creates_principal_and_password_hash(tmp_path: Path) -> None:
    service, store = await _service(tmp_path)

    try:
        principal = await service.register(email="Dev@Example.com", password="password-1")
        stored = await store.principals.get(principal.principal_id)
        binding = await store.principal_vault_bindings.get_default_vault(principal.principal_id)

        assert principal.email == "dev@example.com"
        assert principal.principal_id.startswith("principal_")
        assert principal.password_hash != "password-1"
        assert stored is not None
        assert stored.password_hash == principal.password_hash
        assert binding is not None
    finally:
        await _close(store)


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(tmp_path: Path) -> None:
    service, store = await _service(tmp_path)

    try:
        await service.register(email="dev@example.com", password="password-1")

        with pytest.raises(ValueError, match="already registered"):
            await service.register(email="DEV@example.com", password="password-2")
    finally:
        await _close(store)


@pytest.mark.asyncio
async def test_register_adds_password_to_existing_passwordless_principal(tmp_path: Path) -> None:
    service, store = await _service(tmp_path)

    try:
        existing = await store.principals.create_by_email("dev@example.com")
        registered = await service.register(email="dev@example.com", password="password-1")

        assert registered.principal_id == existing.principal_id
        assert registered.password_hash is not None
    finally:
        await _close(store)


@pytest.mark.asyncio
async def test_login_verifies_password_and_issues_jwt(tmp_path: Path) -> None:
    service, store = await _service(tmp_path)

    try:
        created = await service.register(email="dev@example.com", password="password-1")
        session = await service.login(email="dev@example.com", password="password-1")

        claims = jwt.decode(session.token, "test-secret", algorithms=["HS256"], audience=UI_TOKEN_AUDIENCE)
        assert session.principal_id == created.principal_id
        assert claims["sub"] == created.principal_id
        assert claims["email"] == "dev@example.com"
    finally:
        await _close(store)


@pytest.mark.asyncio
async def test_login_rejects_wrong_password(tmp_path: Path) -> None:
    service, store = await _service(tmp_path)

    try:
        await service.register(email="dev@example.com", password="password-1")

        with pytest.raises(ValueError, match="Invalid email or password"):
            await service.login(email="dev@example.com", password="wrong-password")
    finally:
        await _close(store)


@pytest.mark.asyncio
async def test_change_password_requires_current_password_and_updates_login(tmp_path: Path) -> None:
    service, store = await _service(tmp_path)

    try:
        principal = await service.register(email="dev@example.com", password="password-1")

        with pytest.raises(ValueError, match="Invalid current password"):
            await service.change_password(
                principal_id=principal.principal_id,
                current_password="wrong-password",
                new_password="password-2",
            )

        await service.change_password(
            principal_id=principal.principal_id,
            current_password="password-1",
            new_password="password-2",
        )

        with pytest.raises(ValueError, match="Invalid email or password"):
            await service.login(email="dev@example.com", password="password-1")

        session = await service.login(email="dev@example.com", password="password-2")
        assert session.principal_id == principal.principal_id
    finally:
        await _close(store)
