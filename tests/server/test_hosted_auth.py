from pathlib import Path

import jwt
import pytest

from authsome.server.hosted_auth import UI_TOKEN_AUDIENCE, HostedAccountService
from authsome.server.registries import (
    PrincipalRegistry,
    PrincipalVaultBindingRegistry,
    VaultRegistry,
)


def _service(tmp_path: Path) -> HostedAccountService:
    return HostedAccountService(
        principals=PrincipalRegistry(tmp_path / "principal_registry.json"),
        vaults=VaultRegistry(tmp_path / "vault_registry.json"),
        bindings=PrincipalVaultBindingRegistry(tmp_path / "principal_vault_binding_registry.json"),
        jwt_secret="test-secret",
    )


@pytest.mark.asyncio
async def test_register_creates_principal_and_password_hash(tmp_path: Path) -> None:
    service = _service(tmp_path)

    principal = await service.register(email="Dev@Example.com", password="password-1")
    principals = PrincipalRegistry(tmp_path / "principal_registry.json")
    stored = await principals.get(principal.principal_id)
    bindings = PrincipalVaultBindingRegistry(tmp_path / "principal_vault_binding_registry.json")
    binding = await bindings.get_default_vault(principal.principal_id)

    assert principal.email == "dev@example.com"
    assert principal.principal_id.startswith("principal_")
    assert principal.password_hash != "password-1"
    assert stored is not None
    assert stored.password_hash == principal.password_hash
    assert binding is not None


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(tmp_path: Path) -> None:
    service = _service(tmp_path)

    await service.register(email="dev@example.com", password="password-1")

    with pytest.raises(ValueError, match="already registered"):
        await service.register(email="DEV@example.com", password="password-2")


@pytest.mark.asyncio
async def test_register_adds_password_to_existing_passwordless_principal(tmp_path: Path) -> None:
    principals = PrincipalRegistry(tmp_path / "principal_registry.json")
    existing = await principals.create_by_email("dev@example.com")
    service = _service(tmp_path)

    registered = await service.register(email="dev@example.com", password="password-1")

    assert registered.principal_id == existing.principal_id
    assert registered.password_hash is not None


@pytest.mark.asyncio
async def test_login_verifies_password_and_issues_jwt(tmp_path: Path) -> None:
    service = _service(tmp_path)

    created = await service.register(email="dev@example.com", password="password-1")
    session = await service.login(email="dev@example.com", password="password-1")

    claims = jwt.decode(session.token, "test-secret", algorithms=["HS256"], audience=UI_TOKEN_AUDIENCE)
    assert session.principal_id == created.principal_id
    assert claims["sub"] == created.principal_id
    assert claims["email"] == "dev@example.com"


@pytest.mark.asyncio
async def test_login_rejects_wrong_password(tmp_path: Path) -> None:
    service = _service(tmp_path)

    await service.register(email="dev@example.com", password="password-1")

    with pytest.raises(ValueError, match="Invalid email or password"):
        await service.login(email="dev@example.com", password="wrong-password")
