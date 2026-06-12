import asyncio
import json
from pathlib import Path

from fastapi import status
from fastapi.testclient import TestClient

from authsome.auth.models.connection import AccountInfo, ConnectionRecord, ProviderMetadataRecord
from authsome.auth.models.enums import AuthType, ConnectionStatus
from authsome.cli.identity import RuntimeIdentity
from authsome.server.credential_repository import build_store_key
from tests.server.helpers import create_server_test_client
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


def _put_connection(
    client: TestClient,
    principal_id: str,
    vault_id: str,
    connection: str,
    *,
    api_url: str | None = None,
) -> None:
    collection = f"vault:{vault_id}"
    key = build_store_key(vault=vault_id, provider="github", connection=connection, record_type="connection")
    record = ConnectionRecord(
        provider="github",
        principal_id=principal_id,
        vault_id=vault_id,
        connection_name=connection,
        auth_type=AuthType.OAUTH2,
        status=ConnectionStatus.CONNECTED,
        access_token=f"access-{connection}",
        refresh_token=f"refresh-{connection}",
        token_type="bearer",
        scopes=["repo"],
        account=AccountInfo(label="GitHub Admin"),
        api_url=api_url,
    )
    metadata_key = build_store_key(vault=vault_id, provider="github", record_type="metadata")
    metadata = ProviderMetadataRecord(
        principal_id=principal_id,
        vault_id=vault_id,
        provider="github",
        default_connection=connection,
        connection_names=[connection],
        last_used_connection=connection,
    )
    asyncio.run(client.app.state.vault.put(key, record.model_dump_json(), collection=collection))
    asyncio.run(client.app.state.vault.put(metadata_key, metadata.model_dump_json(), collection=collection))


def test_admin_can_make_connection_global_and_user_sees_redacted_summary(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    with create_server_test_client() as client:
        admin = _claim_identity(client, tmp_path, "admin-ready-boldly-0001", email="admin@example.com")
        user = _claim_identity(client, tmp_path, "steady-wisely-boldly-0042", email="user@example.com")
        admin_ctx = asyncio.run(client.app.state.ownership_resolver.resolve(identity=admin.handle))
        _put_connection(client, admin_ctx.principal_id, admin_ctx.vault_id, "default")

        set_response = client.post(
            "/api/connections/github/default/global",
            headers=_auth_header(tmp_path, "POST", "/api/connections/github/default/global", handle=admin.handle),
        )
        list_response = client.get(
            "/api/connections",
            headers=_auth_header(tmp_path, "GET", "/api/connections", handle=user.handle),
        )
        detail_path = f"/api/connections/github/default/detail?principal={admin_ctx.principal_id}"
        detail_response = client.get(
            detail_path,
            headers=_auth_header(tmp_path, "GET", detail_path, handle=user.handle),
        )
        raw_response = client.get(
            "/api/connections/github/default",
            headers=_auth_header(tmp_path, "GET", "/api/connections/github/default", handle=user.handle),
        )

    assert set_response.status_code == status.HTTP_200_OK
    assert set_response.json() == {"status": "ok", "provider": "github", "connection_name": "default"}
    assert list_response.status_code == status.HTTP_200_OK
    body = list_response.json()
    assert body["connections"] == []
    assert body["global_connections"] == [
        {
            "provider": "github",
            "provider_display_name": "GitHub",
            "connection_name": "default",
            "status": "connected",
            "auth_type": "oauth2",
            "account_label": "GitHub Admin",
            "api_url": None,
            "source": "global",
        }
    ]
    assert "access-default" not in str(body["global_connections"])
    assert detail_response.status_code == status.HTTP_403_FORBIDDEN
    assert raw_response.status_code == status.HTTP_404_NOT_FOUND


def test_global_connection_resolves_for_explicit_default_and_proxy_routes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    with create_server_test_client() as client:
        admin = _claim_identity(client, tmp_path, "admin-ready-boldly-0001", email="admin@example.com")
        user = _claim_identity(client, tmp_path, "steady-wisely-boldly-0042", email="user@example.com")
        admin_ctx = asyncio.run(client.app.state.ownership_resolver.resolve(identity=admin.handle))
        _put_connection(
            client,
            admin_ctx.principal_id,
            admin_ctx.vault_id,
            "shared",
            api_url="api.enterprise-github.test",
        )

        set_response = client.post(
            "/api/connections/github/shared/global",
            headers=_auth_header(tmp_path, "POST", "/api/connections/github/shared/global", handle=admin.handle),
        )
        omitted_body = json.dumps({"provider": "github"}, separators=(",", ":"), sort_keys=True).encode("utf-8")
        omitted_response = client.post(
            "/api/credentials/resolve",
            content=omitted_body,
            headers={
                **_auth_header(tmp_path, "POST", "/api/credentials/resolve", body=omitted_body, handle=user.handle),
                "Content-Type": "application/json",
            },
        )
        explicit_body = json.dumps(
            {"connection": "default", "provider": "github"}, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
        explicit_response = client.post(
            "/api/credentials/resolve",
            content=explicit_body,
            headers={
                **_auth_header(tmp_path, "POST", "/api/credentials/resolve", body=explicit_body, handle=user.handle),
                "Content-Type": "application/json",
            },
        )
        routes_response = client.get(
            "/api/proxy/routes",
            headers=_auth_header(tmp_path, "GET", "/api/proxy/routes", handle=user.handle),
        )

    assert set_response.status_code == status.HTTP_200_OK
    assert omitted_response.status_code == status.HTTP_200_OK
    assert omitted_response.json()["source"] == "global"
    assert omitted_response.json()["connection"] == "shared"
    assert omitted_response.json()["headers"] == {"Authorization": "Bearer access-shared"}
    assert explicit_response.status_code == status.HTTP_200_OK
    assert explicit_response.json()["source"] == "global"
    assert explicit_response.json()["connection"] == "shared"
    assert explicit_response.json()["headers"] == {"Authorization": "Bearer access-shared"}
    assert routes_response.status_code == status.HTTP_200_OK
    assert any(
        route["provider"] == "github"
        and route["connection"] == "default"
        and route["api_url"] == "api.enterprise-github.test"
        for route in routes_response.json()["routes"]
    )


def test_non_admin_cannot_make_connection_global(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    with create_server_test_client() as client:
        _claim_identity(client, tmp_path, "admin-ready-boldly-0001", email="admin@example.com")
        user = _claim_identity(client, tmp_path, "steady-wisely-boldly-0042", email="user@example.com")
        user_ctx = asyncio.run(client.app.state.ownership_resolver.resolve(identity=user.handle))
        _put_connection(client, user_ctx.principal_id, user_ctx.vault_id, "default")

        response = client.post(
            "/api/connections/github/default/global",
            headers=_auth_header(tmp_path, "POST", "/api/connections/github/default/global", handle=user.handle),
        )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "Admin role required"


def test_admin_can_remove_global_connection(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    with create_server_test_client() as client:
        admin = _claim_identity(client, tmp_path, "admin-ready-boldly-0001", email="admin@example.com")
        user = _claim_identity(client, tmp_path, "steady-wisely-boldly-0042", email="user@example.com")
        admin_ctx = asyncio.run(client.app.state.ownership_resolver.resolve(identity=admin.handle))
        _put_connection(client, admin_ctx.principal_id, admin_ctx.vault_id, "default")
        assert (
            client.post(
                "/api/connections/github/default/global",
                headers=_auth_header(tmp_path, "POST", "/api/connections/github/default/global", handle=admin.handle),
            ).status_code
            == status.HTTP_200_OK
        )

        remove_response = client.delete(
            "/api/connections/github/global",
            headers=_auth_header(tmp_path, "DELETE", "/api/connections/github/global", handle=admin.handle),
        )
        list_response = client.get(
            "/api/connections",
            headers=_auth_header(tmp_path, "GET", "/api/connections", handle=user.handle),
        )

    assert remove_response.status_code == status.HTTP_200_OK
    assert remove_response.json() == {"status": "ok", "provider": "github", "deleted": True}
    assert list_response.status_code == status.HTTP_200_OK
    assert list_response.json()["global_connections"] == []
