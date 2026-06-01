import asyncio
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

from fastapi.testclient import TestClient

from authsome import audit
from authsome.auth.models.connection import ConnectionRecord, ProviderMetadataRecord
from authsome.auth.models.enums import AuthType, ConnectionStatus
from authsome.identity import create_identity
from authsome.server.app import create_app
from authsome.server.credential_repository import build_store_key
from authsome.utils import utc_now


def _register_identity_for_claim(client: TestClient, tmp_path: Path, handle: str) -> str:
    identity = create_identity(tmp_path, handle)
    response = client.post("/identities/register", json={"handle": identity.handle, "did": identity.did})
    assert response.status_code == 200
    return urlparse(response.json()["claim_url"]).path


def _register_identity(client: TestClient, tmp_path: Path, handle: str, *, email: str = "dev@example.com") -> None:
    """Register an identity and drive the browser claim flow, leaving the client logged in."""
    claim_path = _register_identity_for_claim(client, tmp_path, handle)
    registered = client.post(
        "/auth/register",
        data={"email": email, "password": "password-1", "next": claim_path},
        follow_redirects=False,
    )
    assert registered.status_code == 303
    assert client.post(f"{claim_path}/confirm", follow_redirects=False).status_code == 303


def _seed_connection(
    client: TestClient,
    *,
    identity: str,
    provider: str,
    auth_type: AuthType,
    connection_name: str = "default",
    access_token: str | None = None,
    refresh_token: str | None = None,
    api_key: str | None = None,
) -> None:
    resolved = asyncio.run(client.app.state.ownership_resolver.resolve(identity=identity))
    record = ConnectionRecord(
        provider=provider,
        identity=identity,
        principal_id=resolved.principal_id,
        vault_id=resolved.vault_id,
        connection_name=connection_name,
        auth_type=auth_type,
        status=ConnectionStatus.CONNECTED,
        access_token=access_token,
        refresh_token=refresh_token,
        api_key=api_key,
        expires_at=utc_now() + timedelta(hours=1),
    )
    asyncio.run(
        client.app.state.vault.put(
            build_store_key(
                vault=resolved.vault_id,
                provider=provider,
                record_type="connection",
                connection=connection_name,
            ),
            record.model_dump_json(),
            collection=f"vault:{resolved.vault_id}",
        )
    )
    asyncio.run(
        client.app.state.vault.put(
            build_store_key(vault=resolved.vault_id, provider=provider, record_type="metadata"),
            ProviderMetadataRecord(
                identity=identity,
                principal_id=resolved.principal_id,
                vault_id=resolved.vault_id,
                provider=provider,
                connection_names=[connection_name],
                default_connection=connection_name,
                last_used_connection=connection_name,
            ).model_dump_json(),
            collection=f"vault:{resolved.vault_id}",
        )
    )


def test_legacy_server_rendered_routes_are_removed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    with TestClient(create_app()) as client:
        responses = {
            path: client.get(path, follow_redirects=False)
            for path in (
                "/legacy",
                "/applications",
                "/manage/connections",
                "/identity",
                "/audit",
                "/apps/github",
                "/apps/github/connections/default",
                "/static/style.css",
            )
        }

    assert {path: response.status_code for path, response in responses.items()} == {
        "/legacy": 404,
        "/applications": 404,
        "/manage/connections": 404,
        "/identity": 404,
        "/audit": 404,
        "/apps/github": 404,
        "/apps/github/connections/default": 404,
        "/static/style.css": 404,
    }


def test_browser_session_can_read_existing_daemon_json_routes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    with TestClient(create_app()) as client:
        _register_identity(client, tmp_path, "steady-wisely-boldly-0042")
        _seed_connection(
            client,
            identity="steady-wisely-boldly-0042",
            provider="github",
            auth_type=AuthType.OAUTH2,
            access_token="gh-access-token",
            refresh_token="gh-refresh-token",
        )
        audit.emit_event(
            "credentials_exported",
            source="external",
            identity="steady-wisely-boldly-0042",
            provider="github",
            status="ok",
            request_id="req-123",
        )
        whoami = client.get("/whoami")
        connections = client.get("/connections")
        audit_events = client.get("/audit/events?limit=10")

    assert whoami.status_code == 200
    assert whoami.json()["account_email"] == "dev@example.com"
    assert whoami.json()["principal_role"] == "admin"
    assert connections.status_code == 200
    assert connections.json()["connections"][0]["name"] == "github"
    assert audit_events.status_code == 200
    assert audit_events.json()["entries"][0]["provider"] == "github"


def test_connect_provider_accepts_connection_name_fallback(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    with TestClient(create_app()) as client:
        _register_identity(client, tmp_path, "steady-wisely-boldly-0042")
        _seed_connection(
            client,
            identity="steady-wisely-boldly-0042",
            provider="github",
            auth_type=AuthType.OAUTH2,
            access_token="gh-access-token",
            refresh_token="gh-refresh-token",
        )
        response = client.post(
            "/auth/providers/github/connect",
            data={"connection_name": "work"},
            follow_redirects=False,
        )
        session = next(
            session
            for session in client.app.state.auth_sessions._sessions.values()
            if session.provider == "github" and session.connection_name == "work"
        )

    assert response.status_code == 303
    assert "/auth/sessions/" in response.headers["location"]
    assert session.payload["return_url"].endswith("/")


def test_connect_provider_redirects_to_root_for_existing_connection(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    with TestClient(create_app()) as client:
        _register_identity(client, tmp_path, "steady-wisely-boldly-0042")
        _seed_connection(
            client,
            identity="steady-wisely-boldly-0042",
            provider="github",
            auth_type=AuthType.OAUTH2,
            access_token="gh-access-token",
            refresh_token="gh-refresh-token",
        )
        response = client.post("/auth/providers/github/connect", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/"
