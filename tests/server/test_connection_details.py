import asyncio
from pathlib import Path

from fastapi import status
from fastapi.testclient import TestClient

from authsome.auth.models.connection import ConnectionRecord, ProviderMetadataRecord
from authsome.auth.models.enums import AuthType, ConnectionStatus
from authsome.cli.identity import RuntimeIdentity
from authsome.server.credential_repository import build_store_key
from authsome.server.routes._deps import UI_SESSION_COOKIE_NAME
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
    auth_type: AuthType = AuthType.OAUTH2,
) -> None:
    collection = f"vault:{vault_id}"
    key = build_store_key(vault=vault_id, provider="github", connection=connection, record_type="connection")
    record = ConnectionRecord(
        provider="github",
        principal_id=principal_id,
        vault_id=vault_id,
        connection_name=connection,
        auth_type=auth_type,
        status=ConnectionStatus.CONNECTED,
        access_token=f"access-{connection}" if auth_type == AuthType.OAUTH2 else None,
        refresh_token=f"refresh-{connection}" if auth_type == AuthType.OAUTH2 else None,
        api_key=f"key-{connection}" if auth_type == AuthType.API_KEY else None,
        token_type="bearer" if auth_type == AuthType.OAUTH2 else None,
        scopes=["repo"] if auth_type == AuthType.OAUTH2 else None,
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


def test_user_can_read_own_connection_detail(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    with create_server_test_client() as client:
        user = _claim_identity(client, tmp_path, "steady-wisely-boldly-0042", email="user@example.com")
        user_ctx = asyncio.run(client.app.state.ownership_resolver.resolve(identity=user.handle))
        _put_connection(client, user_ctx.principal_id, user_ctx.vault_id, "default")
        response = client.get(
            "/api/connections/github/default/detail",
            headers=_auth_header(tmp_path, "GET", "/api/connections/github/default/detail", handle=user.handle),
        )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["connection_name"] == "default"
    assert body["secrets"]["access_token"] == "access-default"
    assert body["secrets"]["refresh_token"] == "refresh-default"


def test_non_admin_cannot_read_other_principal_connection(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    with create_server_test_client() as client:
        _claim_identity(client, tmp_path, "admin-ready-boldly-0001", email="admin@example.com")
        user = _claim_identity(client, tmp_path, "steady-wisely-boldly-0042", email="user@example.com")
        admin_ctx = asyncio.run(client.app.state.ownership_resolver.resolve(identity="admin-ready-boldly-0001"))
        _put_connection(client, admin_ctx.principal_id, admin_ctx.vault_id, "admin-main")
        path = f"/api/connections/github/admin-main/detail?principal={admin_ctx.principal_id}"
        response = client.get(path, headers=_auth_header(tmp_path, "GET", path, handle=user.handle))

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_admin_can_read_other_principal_connection(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    with create_server_test_client() as client:
        admin = _claim_identity(client, tmp_path, "admin-ready-boldly-0001", email="admin@example.com")
        _claim_identity(client, tmp_path, "steady-wisely-boldly-0042", email="user@example.com")
        user_ctx = asyncio.run(client.app.state.ownership_resolver.resolve(identity="steady-wisely-boldly-0042"))
        _put_connection(client, user_ctx.principal_id, user_ctx.vault_id, "user-main")
        path = f"/api/connections/github/user-main/detail?principal={user_ctx.principal_id}"
        response = client.get(path, headers=_auth_header(tmp_path, "GET", path, handle=admin.handle))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["principal_id"] == user_ctx.principal_id
    assert response.json()["secrets"]["access_token"] == "access-user-main"


def test_admin_logout_targets_other_principal_connection(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    with create_server_test_client() as client:
        admin = _claim_identity(client, tmp_path, "admin-ready-boldly-0001", email="admin@example.com")
        _claim_identity(client, tmp_path, "steady-wisely-boldly-0042", email="user@example.com")
        user_ctx = asyncio.run(client.app.state.ownership_resolver.resolve(identity="steady-wisely-boldly-0042"))
        _put_connection(client, user_ctx.principal_id, user_ctx.vault_id, "user-main", auth_type=AuthType.API_KEY)
        path = f"/api/connections/github/user-main/logout?principal={user_ctx.principal_id}"
        response = client.post(path, headers=_auth_header(tmp_path, "POST", path, handle=admin.handle))
        assert response.status_code == status.HTTP_200_OK

        detail_path = f"/api/connections/github/user-main/detail?principal={user_ctx.principal_id}"
        missing = client.get(detail_path, headers=_auth_header(tmp_path, "GET", detail_path, handle=admin.handle))

    assert missing.status_code == status.HTTP_404_NOT_FOUND


def test_admin_browser_session_can_revoke_provider(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    with create_server_test_client() as client:
        admin = _claim_identity(client, tmp_path, "admin-ready-boldly-0001", email="admin@example.com")
        admin_ctx = asyncio.run(client.app.state.ownership_resolver.resolve(identity=admin.handle))
        _put_connection(client, admin_ctx.principal_id, admin_ctx.vault_id, "default", auth_type=AuthType.API_KEY)
        session = client.app.state.ui_sessions.create_browser_session(
            principal_id=admin_ctx.principal_id,
            email="admin@example.com",
        )
        client.cookies.set(UI_SESSION_COOKIE_NAME, client.app.state.ui_sessions.build_cookie_value(session.token))

        response = client.post("/api/connections/github/revoke", json={})
        assert response.status_code == status.HTTP_200_OK

        detail = client.get(
            "/api/connections/github/default/detail",
            headers=_auth_header(tmp_path, "GET", "/api/connections/github/default/detail", handle=admin.handle),
        )

    assert detail.status_code == status.HTTP_404_NOT_FOUND
