import asyncio
from pathlib import Path
from urllib.parse import urlparse

from fastapi.testclient import TestClient

from authsome.auth.models.connection import ProviderClientRecord
from authsome.identity import create_identity, load_private_key
from authsome.identity.proof import create_proof_jwt
from authsome.server.app import create_app
from authsome.utils import build_store_key


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
    claim_url = response.json().get("claim_url")
    if claim_url:
        claim_path = urlparse(claim_url).path
        claim_page = client.get(claim_path)
        assert claim_page.status_code == 200
        claimed = client.post(claim_path, data={"email": "dev@example.com"}, follow_redirects=False)
        assert claimed.status_code == 303


def test_hosted_ui_requires_browser_session(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.setenv("AUTHSOME_DEPLOYMENT_MODE", "hosted")

    with TestClient(create_app()) as client:
        response = client.get("/ui/")

    assert response.status_code == 401
    assert "authsome ui" in response.text


def test_hosted_ui_bootstrap_sets_cookie_and_opens_dashboard(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.setenv("AUTHSOME_DEPLOYMENT_MODE", "hosted")

    with TestClient(create_app()) as client:
        _register_identity(client, tmp_path, "steady-wisely-boldly-0042")
        bootstrap_response = client.post(
            "/ui/session",
            headers=_auth_header(tmp_path, "POST", "/ui/session", handle="steady-wisely-boldly-0042"),
        )
        assert bootstrap_response.status_code == 200
        bootstrap_url = bootstrap_response.json()["url"]
        bootstrap_path = urlparse(bootstrap_url).path

        handoff_response = client.get(bootstrap_path, follow_redirects=False)
        assert handoff_response.status_code == 303
        assert "authsome_ui_session=" in handoff_response.headers.get("set-cookie", "")

        dashboard_response = client.get("/ui/")

    assert dashboard_response.status_code == 200
    assert "Signed in as steady-wisely-boldly-0042" in dashboard_response.text


def test_hosted_ui_hides_server_managed_oauth_client_details(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.setenv("AUTHSOME_DEPLOYMENT_MODE", "hosted")

    with TestClient(create_app()) as client:
        _register_identity(client, tmp_path, "steady-wisely-boldly-0042")
        vault = client.app.state.vault
        key = build_store_key(provider="github", record_type="server")
        record = ProviderClientRecord(provider="github", client_id="cid-123", client_secret="top-secret")
        asyncio.run(vault.put(key, record.model_dump_json(), collection="server"))

        bootstrap_response = client.post(
            "/ui/session",
            headers=_auth_header(tmp_path, "POST", "/ui/session", handle="steady-wisely-boldly-0042"),
        )
        bootstrap_path = urlparse(bootstrap_response.json()["url"]).path
        client.get(bootstrap_path, follow_redirects=False)

        response = client.get("/ui/apps/github")

    assert response.status_code == 200
    assert "cid-123" not in response.text
    assert "manages the OAuth application" in response.text


def test_hosted_ui_auth_input_requires_matching_browser_session(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.setenv("AUTHSOME_DEPLOYMENT_MODE", "hosted")

    app = create_app()
    with TestClient(app) as client:
        _register_identity(client, tmp_path, "steady-wisely-boldly-0042")
        session = asyncio.run(
            client.app.state.auth_sessions.create(
                provider="github",
                identity="steady-wisely-boldly-0042",
                principal_id="principal_test",
                connection_name="default",
                flow_type="pkce",
            )
        )
        session.payload["ui_session_required"] = True
        session.payload["input_fields"] = [{"name": "client_id", "label": "Client ID", "secret": False}]
        asyncio.run(client.app.state.auth_sessions.save(session))

        response = client.get(f"/auth/sessions/{session.session_id}/input")

    assert response.status_code == 401
    assert "authsome ui" in response.text
