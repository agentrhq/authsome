import asyncio
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

from fastapi.testclient import TestClient

from authsome.auth.models.connection import ConnectionRecord, ProviderMetadataRecord
from authsome.auth.models.enums import AuthType, ConnectionStatus
from authsome.identity import create_identity, load_private_key
from authsome.identity.proof import create_proof_jwt
from authsome.server.app import create_app
from authsome.utils import build_store_key, utc_now


def _auth_header(tmp_path: Path, method: str, path: str, *, handle: str) -> dict[str, str]:
    identity = create_identity(tmp_path, handle)
    token = create_proof_jwt(
        private_key=load_private_key(tmp_path, identity.handle),
        issuer=identity.did,
        subject=identity.handle,
        method=method,
        path_query=path,
        body=b"",
    )
    return {"Authorization": f"PoP {token}"}


def _register_identity(client: TestClient, tmp_path: Path, handle: str) -> None:
    identity = create_identity(tmp_path, handle)
    response = client.post("/identities/register", json={"handle": identity.handle, "did": identity.did})
    assert response.status_code == 200


def _register_identity_for_claim(client: TestClient, tmp_path: Path, handle: str) -> str:
    identity = create_identity(tmp_path, handle)
    response = client.post("/identities/register", json={"handle": identity.handle, "did": identity.did})
    assert response.status_code == 200
    return urlparse(response.json()["claim_url"]).path


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


def _seed_provider_client(
    client: TestClient,
    *,
    provider: str,
    client_id: str,
    client_secret: str | None = None,
) -> None:
    from authsome.auth.models.connection import ProviderClientRecord

    asyncio.run(
        client.app.state.vault.put(
            build_store_key(provider=provider, record_type="server"),
            ProviderClientRecord(
                provider=provider,
                client_id=client_id,
                client_secret=client_secret,
            ).model_dump_json(),
            collection="server",
        )
    )


def test_overview_navigation_shows_applications_connections_and_identity(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.delenv("AUTHSOME_DEPLOYMENT_MODE", raising=False)

    with TestClient(create_app()) as client:
        _register_identity(client, tmp_path, "steady-wisely-boldly-0042")
        response = client.get("/ui/")

    assert response.status_code == 200
    assert "Overview" in response.text
    assert "Applications" in response.text
    assert "Connections" in response.text
    assert "Identity" in response.text


def test_applications_page_renders_provider_catalog(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.delenv("AUTHSOME_DEPLOYMENT_MODE", raising=False)

    with TestClient(create_app()) as client:
        _register_identity(client, tmp_path, "steady-wisely-boldly-0042")
        response = client.get("/ui/applications")

    assert response.status_code == 200
    assert "Applications" in response.text


def test_applications_page_shows_provider_login_action(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.delenv("AUTHSOME_DEPLOYMENT_MODE", raising=False)

    with TestClient(create_app()) as client:
        _register_identity(client, tmp_path, "steady-wisely-boldly-0042")
        response = client.get("/ui/applications")

    assert response.status_code == 200
    assert 'action="/ui/apps/github/connect"' in response.text
    assert "Login" in response.text


def test_identity_page_renders_informational_identity_view(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.delenv("AUTHSOME_DEPLOYMENT_MODE", raising=False)

    with TestClient(create_app()) as client:
        _register_identity(client, tmp_path, "steady-wisely-boldly-0042")
        response = client.get("/ui/identity")

    assert response.status_code == 200
    assert "Identity" in response.text
    assert "steady-wisely-boldly-0042" in response.text


def test_hosted_identity_page_lists_all_account_claims(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.setenv("AUTHSOME_DEPLOYMENT_MODE", "hosted")

    with TestClient(create_app()) as client:
        first_claim = _register_identity_for_claim(client, tmp_path, "steady-wisely-boldly-0042")
        registered = client.post(
            "/ui/auth/register",
            data={"email": "dev@example.com", "password": "password-1", "next": first_claim},
            follow_redirects=False,
        )
        assert registered.status_code == 303
        assert client.post(f"{first_claim}/confirm", follow_redirects=False).status_code == 303

        second_claim = _register_identity_for_claim(client, tmp_path, "brave-softly-surely-0043")
        assert "dev@example.com" in client.get(second_claim).text
        assert client.post(f"{second_claim}/confirm", follow_redirects=False).status_code == 303

        response = client.get("/ui/identity")

    assert response.status_code == 200
    assert "Signed in as dev@example.com" in response.text
    assert "steady-wisely-boldly-0042" in response.text
    assert "brave-softly-surely-0043" in response.text


def test_hosted_applications_redirects_to_ui_login_entry(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.setenv("AUTHSOME_DEPLOYMENT_MODE", "hosted")

    with TestClient(create_app()) as client:
        response = client.get("/ui/applications", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/ui/?next=%2Fui%2Fapplications"


def test_provider_page_shows_provider_configuration_not_connection_tokens(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.delenv("AUTHSOME_DEPLOYMENT_MODE", raising=False)

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
        response = client.get("/ui/apps/github")

    assert response.status_code == 200
    assert "OAuth Application" in response.text or "Managed by Authsome" in response.text
    assert "Access Token" not in response.text


def test_named_connection_detail_route_exists(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.delenv("AUTHSOME_DEPLOYMENT_MODE", raising=False)

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
        response = client.get("/ui/apps/github/connections/default")

    assert response.status_code == 200


def test_named_connection_detail_page_shows_oauth_tokens(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.delenv("AUTHSOME_DEPLOYMENT_MODE", raising=False)

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
        response = client.get("/ui/apps/github/connections/default")

    assert response.status_code == 200
    assert "Access Token" in response.text
    assert "Refresh Token" in response.text
    assert "Client ID" not in response.text
    assert "Client Secret" not in response.text
    assert "Redirect URI" not in response.text
    assert "Authorization URL" not in response.text
    assert "Token URL" not in response.text


def test_named_connection_detail_page_shows_api_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.delenv("AUTHSOME_DEPLOYMENT_MODE", raising=False)

    with TestClient(create_app()) as client:
        _register_identity(client, tmp_path, "steady-wisely-boldly-0042")
        _seed_connection(
            client,
            identity="steady-wisely-boldly-0042",
            provider="openai",
            auth_type=AuthType.API_KEY,
            api_key="sk-test-key",
        )
        response = client.get("/ui/apps/openai/connections/default")

    assert response.status_code == 200
    assert "API Credentials" in response.text


def test_provider_page_for_api_key_provider_omits_provider_setup_section(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.delenv("AUTHSOME_DEPLOYMENT_MODE", raising=False)

    with TestClient(create_app()) as client:
        _register_identity(client, tmp_path, "steady-wisely-boldly-0042")
        _seed_connection(
            client,
            identity="steady-wisely-boldly-0042",
            provider="openai",
            auth_type=AuthType.API_KEY,
            api_key="sk-test-key",
        )
        response = client.get("/ui/apps/openai")

    assert response.status_code == 200
    assert "OAuth Application" not in response.text
    assert "API Credentials" not in response.text


def test_provider_page_lists_existing_connections_as_read_only_context(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.delenv("AUTHSOME_DEPLOYMENT_MODE", raising=False)

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
        response = client.get("/ui/apps/github")

    assert response.status_code == 200
    assert "Existing connections" in response.text


def test_connections_page_renders_connection_rows(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.delenv("AUTHSOME_DEPLOYMENT_MODE", raising=False)

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
        response = client.get("/ui/connections")

    assert response.status_code == 200
    assert "Add new connection" in response.text
    assert "connection-row" in response.text


def test_provider_login_modal_copy_is_rendered_when_default_exists(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.delenv("AUTHSOME_DEPLOYMENT_MODE", raising=False)

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
        response = client.get("/ui/applications")

    assert response.status_code == 200
    assert "Connection name" in response.text


def test_connect_app_accepts_connection_name_fallback(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.delenv("AUTHSOME_DEPLOYMENT_MODE", raising=False)

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
            "/ui/apps/github/connect",
            data={"connection_name": "work"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert "/auth/sessions/" in response.headers["location"]
    assert any(
        session.provider == "github" and session.connection_name == "work"
        for session in client.app.state.auth_sessions._sessions.values()
    )


def test_provider_page_shows_configure_action_for_oauth(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.delenv("AUTHSOME_DEPLOYMENT_MODE", raising=False)

    with TestClient(create_app()) as client:
        _register_identity(client, tmp_path, "steady-wisely-boldly-0042")
        _seed_provider_client(client, provider="github", client_id="cid-123", client_secret="secret-123")
        response = client.get("/ui/apps/github")

    assert response.status_code == 200
    assert 'action="/ui/apps/github/configure"' in response.text
    assert "Replace" in response.text


def test_provider_configure_route_opens_edit_flow_with_existing_values(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.delenv("AUTHSOME_DEPLOYMENT_MODE", raising=False)

    with TestClient(create_app()) as client:
        _register_identity(client, tmp_path, "steady-wisely-boldly-0042")
        _seed_provider_client(client, provider="github", client_id="cid-123", client_secret="secret-123")
        response = client.post("/ui/apps/github/configure", follow_redirects=False)

    assert response.status_code == 303
    assert "/auth/sessions/" in response.headers["location"]
    session = next(iter(client.app.state.auth_sessions._sessions.values()))
    assert session.payload["provider_config_only"] is True
    fields = session.payload["input_fields"]
    assert any(field["name"] == "client_id" and field["default"] == "cid-123" for field in fields)


def test_provider_configure_input_page_shows_revoke_warning(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.delenv("AUTHSOME_DEPLOYMENT_MODE", raising=False)

    with TestClient(create_app()) as client:
        _register_identity(client, tmp_path, "steady-wisely-boldly-0042")
        _seed_provider_client(client, provider="github", client_id="cid-123", client_secret="secret-123")
        configure = client.post("/ui/apps/github/configure", follow_redirects=False)
        response = client.get(configure.headers["location"])

    assert response.status_code == 200
    assert "Changing these credentials will revoke existing connections for this provider." in response.text


def test_provider_config_submit_replaces_client_and_revokes_connections(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.delenv("AUTHSOME_DEPLOYMENT_MODE", raising=False)

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
        _seed_provider_client(client, provider="github", client_id="cid-123", client_secret="secret-123")

        configure = client.post("/ui/apps/github/configure", follow_redirects=False)
        session_id = configure.headers["location"].rstrip("/").split("/")[-2]
        response = client.post(
            f"/auth/sessions/{session_id}/input",
            data={"client_id": "cid-456", "client_secret": "secret-456"},
            follow_redirects=False,
        )

        provider_client = asyncio.run(
            client.app.state.vault.get(build_store_key(provider="github", record_type="server"), collection="server")
        )
        connections_page = client.get("/ui/connections")

    assert response.status_code == 303
    assert response.headers["location"].endswith("/ui/apps/github")
    assert provider_client is not None
    assert "cid-456" in provider_client
    assert "No connections yet" in connections_page.text
