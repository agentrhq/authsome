import asyncio
from pathlib import Path
from urllib.parse import urlparse

from fastapi.testclient import TestClient

from authsome.auth.models.connection import ProviderClientRecord
from authsome.identity import create_identity, load_private_key
from authsome.identity.proof import create_proof_jwt
from authsome.server.app import create_app
from authsome.server.ui_sessions import UiSessionStore
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


def _claim_identity_via_hosted_ui(client: TestClient, tmp_path: Path, handle: str, email: str) -> None:
    identity = create_identity(tmp_path, handle)
    response = client.post("/identities/register", json={"handle": identity.handle, "did": identity.did})
    assert response.status_code == 200
    claim_path = urlparse(response.json()["claim_url"]).path
    registered = client.post(
        "/ui/auth/register",
        data={"email": email, "password": "password-1", "next": claim_path},
        follow_redirects=False,
    )
    assert registered.status_code == 303
    confirmed = client.post(f"{claim_path}/confirm", follow_redirects=False)
    assert confirmed.status_code == 303


def test_create_pending_claim_and_consume_once() -> None:
    store = UiSessionStore("test-secret")

    token = store.create_pending_claim(identity="steady-wisely-boldly-0042")
    resolved = store.get_pending_claim(token.token)
    consumed = store.consume_pending_claim(token.token)

    assert resolved.identity == "steady-wisely-boldly-0042"
    assert consumed.identity == "steady-wisely-boldly-0042"


def test_consume_pending_claim_rejects_reuse() -> None:
    store = UiSessionStore("test-secret")

    token = store.create_pending_claim(identity="steady-wisely-boldly-0042")
    store.consume_pending_claim(token.token)

    try:
        store.consume_pending_claim(token.token)
    except KeyError:
        pass
    else:
        raise AssertionError("Expected pending claim token reuse to fail")


def test_build_cookie_round_trips_hosted_browser_session() -> None:
    store = UiSessionStore("test-secret")

    session = store.create_browser_session(principal_id="principal_123", email="dev@example.com")
    cookie_value = store.build_cookie_value(session.token)
    parsed = store.get_browser_session(cookie_value)

    assert parsed.principal_id == "principal_123"
    assert parsed.email == "dev@example.com"


def test_hosted_ui_homepage_shows_auth_tabs(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.setenv("AUTHSOME_DEPLOYMENT_MODE", "hosted")

    with TestClient(create_app()) as client:
        response = client.get("/ui/")

    assert response.status_code == 200
    assert "Open dashboard" in response.text
    assert "Sign in" in response.text
    assert "Create account" in response.text


def test_hosted_claim_page_shows_auth_tabs_for_unauthenticated_users(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.setenv("AUTHSOME_DEPLOYMENT_MODE", "hosted")

    with TestClient(create_app()) as client:
        identity = create_identity(tmp_path, "steady-wisely-boldly-0042")
        response = client.post("/identities/register", json={"handle": identity.handle, "did": identity.did})
        assert response.status_code == 200
        claim_path = urlparse(response.json()["claim_url"]).path

        claim_response = client.get(claim_path)

    assert claim_response.status_code == 200
    assert "Sign in" in claim_response.text
    assert "Create account" in claim_response.text


def test_hosted_ui_session_returns_dashboard_url_without_browser_cookie(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.setenv("AUTHSOME_DEPLOYMENT_MODE", "hosted")

    with TestClient(create_app()) as client:
        _claim_identity_via_hosted_ui(client, tmp_path, "steady-wisely-boldly-0042", "dev@example.com")
        bootstrap_response = client.post(
            "/ui/session",
            headers=_auth_header(tmp_path, "POST", "/ui/session", handle="steady-wisely-boldly-0042"),
        )
        assert bootstrap_response.status_code == 200
        assert urlparse(bootstrap_response.json()["url"]).path == "/ui/"
        assert "authsome_ui_session=" not in bootstrap_response.headers.get("set-cookie", "")

        client.cookies.clear()
        dashboard_response = client.get("/ui/")

    assert dashboard_response.status_code == 200
    assert "Open dashboard" in dashboard_response.text


def test_hosted_homepage_registration_redirects_to_dashboard(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.setenv("AUTHSOME_DEPLOYMENT_MODE", "hosted")

    with TestClient(create_app()) as client:
        registered = client.post(
            "/ui/auth/register",
            data={"email": "dev@example.com", "password": "password-1", "next": "/ui/"},
            follow_redirects=False,
        )
        dashboard_response = client.get("/ui/")

    assert registered.status_code == 303
    assert registered.headers["location"] == "/ui/"
    assert dashboard_response.status_code == 200
    assert "Overview" in dashboard_response.text
    assert "Signed in as dev@example.com" in dashboard_response.text


def test_hosted_ui_hides_server_managed_oauth_client_details(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.setenv("AUTHSOME_DEPLOYMENT_MODE", "hosted")

    with TestClient(create_app()) as client:
        _claim_identity_via_hosted_ui(client, tmp_path, "steady-wisely-boldly-0042", "dev@example.com")
        vault = client.app.state.vault
        key = build_store_key(provider="github", record_type="server")
        record = ProviderClientRecord(provider="github", client_id="cid-123", client_secret="top-secret")
        asyncio.run(vault.put(key, record.model_dump_json(), collection="server"))

        response = client.get("/ui/apps/github")

    assert response.status_code == 200
    assert "cid-123" not in response.text
    assert "manages the OAuth application" in response.text
    assert "Existing connections" not in response.text


def test_hosted_ui_connect_starts_principal_scoped_session_without_pop(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.setenv("AUTHSOME_DEPLOYMENT_MODE", "hosted")

    with TestClient(create_app()) as client:
        _claim_identity_via_hosted_ui(client, tmp_path, "steady-wisely-boldly-0042", "dev@example.com")

        response = client.post("/ui/apps/openai/connect", follow_redirects=False)
        session = next(iter(client.app.state.auth_sessions._sessions.values()))

    assert response.status_code == 303
    assert "/auth/sessions/" in response.headers["location"]
    assert session.identity is None
    assert session.principal_id is not None
    assert session.payload["ui_session_required"] is True


def test_hosted_auth_rejects_external_next_redirect(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.setenv("AUTHSOME_DEPLOYMENT_MODE", "hosted")

    with TestClient(create_app()) as client:
        response = client.post(
            "/ui/auth/register",
            data={"email": "dev@example.com", "password": "password-1", "next": "https://example.test"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/ui/"


def test_hosted_homepage_login_error_renders_auth_page(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.setenv("AUTHSOME_DEPLOYMENT_MODE", "hosted")

    with TestClient(create_app()) as client:
        client.post(
            "/ui/auth/register",
            data={"email": "dev@example.com", "password": "password-1", "next": "/ui/"},
            follow_redirects=False,
        )
        client.cookies.clear()
        response = client.post(
            "/ui/auth/login",
            data={"email": "dev@example.com", "password": "wrong-password", "next": "/ui/"},
            follow_redirects=False,
        )

    assert response.status_code == 400
    assert "Invalid email or password" in response.text
    assert "Sign in" in response.text
    assert "Create account" in response.text


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
