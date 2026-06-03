import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from authsome.identity import create_identity
from authsome.server.app import create_app
from tests.server.test_pop_auth import _auth_header


def _register_identity(client: TestClient, tmp_path: Path, handle: str, *, email: str = "dev@example.com") -> None:
    identity = create_identity(tmp_path, handle)
    response = client.post("/api/identities/register", json={"handle": identity.handle, "did": identity.did})
    assert response.status_code == 200
    claim_url = response.json().get("claim_url")
    if claim_url:
        parsed = urlparse(claim_url)
        token = parse_qs(parsed.query)["token"][0]
        claim_path = f"/api/claim/{token}"
        assert client.get(claim_path).status_code == 200
        registered = client.post(
            "/api/auth/register",
            data={"email": email, "password": "password-1", "next": claim_path},
            follow_redirects=False,
        )
        assert registered.status_code == 303
        claimed = client.post(f"{claim_path}/confirm", follow_redirects=False)
        assert claimed.status_code == 303


def _register_admin_then_user(client: TestClient, tmp_path: Path, user_handle: str) -> None:
    _register_identity(client, tmp_path, "admin-ready-boldly-0001", email="admin@example.com")
    _register_identity(client, tmp_path, user_handle, email="user@example.com")


def test_non_admin_revoke_is_rejected(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    with TestClient(create_app()) as client:
        _register_admin_then_user(client, tmp_path, "steady-wisely-boldly-0042")
        response = client.post(
            "/api/connections/github/revoke",
            headers=_auth_header(tmp_path, "POST", "/api/connections/github/revoke"),
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin role required"


def test_non_admin_remove_is_rejected(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    with TestClient(create_app()) as client:
        _register_admin_then_user(client, tmp_path, "steady-wisely-boldly-0042")
        response = client.delete(
            "/api/providers/github",
            headers=_auth_header(tmp_path, "DELETE", "/api/providers/github"),
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin role required"


def test_non_admin_register_provider_is_rejected(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    payload = {
        "definition": {
            "name": "custom-api",
            "display_name": "Custom API",
            "auth_type": "api_key",
            "flow": "api_key",
            "api_key": {"header_name": "Authorization"},
        }
    }
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

    with TestClient(create_app()) as client:
        _register_admin_then_user(client, tmp_path, "steady-wisely-boldly-0042")
        response = client.post(
            "/api/providers",
            content=body,
            headers={
                **_auth_header(tmp_path, "POST", "/api/providers", body=body),
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin role required"


def test_first_principal_admin_can_register_provider(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    payload = {
        "definition": {
            "name": "custom-api",
            "display_name": "Custom API",
            "auth_type": "api_key",
            "flow": "api_key",
            "api_key": {"header_name": "Authorization"},
        }
    }
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

    with TestClient(create_app()) as client:
        _register_identity(client, tmp_path, "steady-wisely-boldly-0042")
        response = client.post(
            "/api/providers",
            content=body,
            headers={
                **_auth_header(tmp_path, "POST", "/api/providers", body=body),
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
