import asyncio
from pathlib import Path

from fastapi import status
from fastapi.testclient import TestClient

from authsome.auth.models.connection import ConnectionRecord, ProviderClientRecord, ProviderMetadataRecord
from authsome.auth.models.enums import AuthType, ConnectionStatus
from authsome.cli.identity import RuntimeIdentity
from authsome.server.app import create_app
from authsome.server.credential_repository import build_store_key
from tests.server.test_pop_auth import _auth_header


def _claim_identity(client: TestClient, tmp_path: Path, handle: str, *, email: str) -> RuntimeIdentity:
    identity = RuntimeIdentity.create(tmp_path, handle)
    response = client.post("/api/identities/register", json={"handle": identity.handle, "did": identity.did})
    assert response.status_code == status.HTTP_200_OK

    async def claim() -> None:
        principal = await client.app.state.store.principals.create_by_email(email)
        vault = await client.app.state.store.vaults.create_default()
        await client.app.state.store.principal_vault_bindings.bind_default(principal.principal_id, vault.vault_id)
        await client.app.state.store.identity_claims.claim_identity(identity.handle, principal.principal_id)
        await client.app.state.store.identity_claims.accept_claim(identity.handle)

    asyncio.run(claim())
    return identity


def _put_provider_client(client: TestClient, provider: str = "github") -> None:
    key = build_store_key(provider=provider, record_type="server")
    record = ProviderClientRecord(
        provider=provider,
        client_id="client-123",
        client_secret="secret-456",
        scopes=["repo", "read:user"],
    )
    asyncio.run(client.app.state.vault.put(key, record.model_dump_json(), collection="server"))


def _put_connection(client: TestClient, principal_id: str, vault_id: str, provider: str, connection: str) -> None:
    collection = f"vault:{vault_id}"
    key = build_store_key(vault=vault_id, provider=provider, connection=connection, record_type="connection")
    record = ConnectionRecord(
        provider=provider,
        principal_id=principal_id,
        vault_id=vault_id,
        connection_name=connection,
        auth_type=AuthType.OAUTH2,
        status=ConnectionStatus.CONNECTED,
        access_token=f"access-{connection}",
        refresh_token=f"refresh-{connection}",
        token_type="bearer",
        scopes=["repo"],
    )
    metadata_key = build_store_key(vault=vault_id, provider=provider, record_type="metadata")
    metadata = ProviderMetadataRecord(
        principal_id=principal_id,
        vault_id=vault_id,
        provider=provider,
        default_connection=connection,
        connection_names=[connection],
        last_used_connection=connection,
    )
    asyncio.run(client.app.state.vault.put(key, record.model_dump_json(), collection=collection))
    asyncio.run(client.app.state.vault.put(metadata_key, metadata.model_dump_json(), collection=collection))


def test_non_admin_provider_detail_hides_config_and_shows_own_connections(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    with TestClient(create_app()) as client:
        _claim_identity(client, tmp_path, "admin-ready-boldly-0001", email="admin@example.com")
        user = _claim_identity(client, tmp_path, "steady-wisely-boldly-0042", email="user@example.com")
        admin_ctx = asyncio.run(client.app.state.ownership_resolver.resolve(identity="admin-ready-boldly-0001"))
        user_ctx = asyncio.run(client.app.state.ownership_resolver.resolve(identity=user.handle))
        _put_provider_client(client)
        _put_connection(client, admin_ctx.principal_id, admin_ctx.vault_id, "github", "admin-main")
        _put_connection(client, user_ctx.principal_id, user_ctx.vault_id, "github", "user-main")

        response = client.get(
            "/api/providers/github/detail",
            headers=_auth_header(tmp_path, "GET", "/api/providers/github/detail", handle=user.handle),
        )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["account"]["is_admin"] is False
    assert body["client"] is None
    assert body["show_callback_helper"] is False
    assert [conn["connection_name"] for conn in body["connections"]] == ["user-main"]
    assert body["principal_usage"] == []


def test_admin_provider_detail_shows_config_and_principal_usage(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    with TestClient(create_app()) as client:
        admin = _claim_identity(client, tmp_path, "admin-ready-boldly-0001", email="admin@example.com")
        _claim_identity(client, tmp_path, "steady-wisely-boldly-0042", email="user@example.com")
        admin_ctx = asyncio.run(client.app.state.ownership_resolver.resolve(identity=admin.handle))
        user_ctx = asyncio.run(client.app.state.ownership_resolver.resolve(identity="steady-wisely-boldly-0042"))
        _put_provider_client(client)
        _put_connection(client, admin_ctx.principal_id, admin_ctx.vault_id, "github", "admin-main")
        _put_connection(client, user_ctx.principal_id, user_ctx.vault_id, "github", "user-main")

        response = client.get(
            "/api/providers/github/detail",
            headers=_auth_header(tmp_path, "GET", "/api/providers/github/detail", handle=admin.handle),
        )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["account"]["is_admin"] is True
    assert body["client"]["client_id"] == "client-123"
    assert body["client"]["client_secret"] == "secret-456"
    assert body["configuration_warning"] == (
        "Changing these credentials will revoke existing connections for this provider."
    )
    field_names = {field["name"] for field in body["configuration_fields"]}
    assert {"client_id", "client_secret", "scopes"}.issubset(field_names)
    assert body["show_callback_helper"] is True
    usage = {group["principal_id"]: group["connections"] for group in body["principal_usage"]}
    assert [conn["connection_name"] for conn in usage[admin_ctx.principal_id]] == ["admin-main"]
    assert [conn["connection_name"] for conn in usage[user_ctx.principal_id]] == ["user-main"]


def test_admin_can_update_provider_configuration(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    with TestClient(create_app()) as client:
        admin = _claim_identity(client, tmp_path, "admin-ready-boldly-0001", email="admin@example.com")
        body = b'{"client_id":"new-client","client_secret":"new-secret","scopes":"repo,read:user"}'
        response = client.put(
            "/api/providers/github/configuration",
            content=body,
            headers={
                **_auth_header(tmp_path, "PUT", "/api/providers/github/configuration", body=body, handle=admin.handle),
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok", "changed": True, "provider": "github"}


def test_non_admin_provider_configuration_update_is_rejected(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    with TestClient(create_app()) as client:
        _claim_identity(client, tmp_path, "admin-ready-boldly-0001", email="admin@example.com")
        user = _claim_identity(client, tmp_path, "steady-wisely-boldly-0042", email="user@example.com")
        body = b'{"client_id":"new-client"}'
        response = client.put(
            "/api/providers/github/configuration",
            content=body,
            headers={
                **_auth_header(tmp_path, "PUT", "/api/providers/github/configuration", body=body, handle=user.handle),
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "Admin role required"
