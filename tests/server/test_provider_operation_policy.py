import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi import status
from fastapi.testclient import TestClient

from authsome.cli.identity import RuntimeIdentity
from tests.server.helpers import create_server_test_client
from tests.server.test_pop_auth import _auth_header


def _register_identity(client: TestClient, tmp_path: Path, handle: str, *, email: str = "dev@example.com") -> None:
    identity = RuntimeIdentity.create(tmp_path, handle)
    response = client.post("/api/identities/register", json={"handle": identity.handle, "did": identity.did})
    assert response.status_code == status.HTTP_200_OK
    claim_url = response.json().get("claim_url")
    if claim_url:
        parsed = urlparse(claim_url)
        token = parse_qs(parsed.query)["token"][0]
        claim_path = f"/api/claim/{token}"
        assert client.get(claim_path).status_code == status.HTTP_200_OK
        registered = client.post(
            "/api/auth/register",
            data={"email": email, "password": "password-1", "next": claim_path},
            follow_redirects=False,
        )
        assert registered.status_code == status.HTTP_303_SEE_OTHER
        claimed = client.post(f"{claim_path}/confirm", follow_redirects=False)
        assert claimed.status_code == status.HTTP_303_SEE_OTHER


def _register_admin_then_user(client: TestClient, tmp_path: Path, user_handle: str) -> None:
    _register_identity(client, tmp_path, "admin-ready-boldly-0001", email="admin@example.com")
    _register_identity(client, tmp_path, user_handle, email="user@example.com")


def test_non_admin_revoke_is_rejected(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    with create_server_test_client() as client:
        _register_admin_then_user(client, tmp_path, "steady-wisely-boldly-0042")
        response = client.post(
            "/api/connections/github/revoke",
            headers=_auth_header(tmp_path, "POST", "/api/connections/github/revoke"),
        )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "Admin role required"


def test_non_admin_remove_is_rejected(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    with create_server_test_client() as client:
        _register_admin_then_user(client, tmp_path, "steady-wisely-boldly-0042")
        response = client.delete(
            "/api/providers/github",
            headers=_auth_header(tmp_path, "DELETE", "/api/providers/github"),
        )

    assert response.status_code == status.HTTP_403_FORBIDDEN
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

    with create_server_test_client() as client:
        _register_admin_then_user(client, tmp_path, "steady-wisely-boldly-0042")
        response = client.post(
            "/api/providers",
            content=body,
            headers={
                **_auth_header(tmp_path, "POST", "/api/providers", body=body),
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == status.HTTP_403_FORBIDDEN
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

    with create_server_test_client() as client:
        _register_identity(client, tmp_path, "steady-wisely-boldly-0042")
        response = client.post(
            "/api/providers",
            content=body,
            headers={
                **_auth_header(tmp_path, "POST", "/api/providers", body=body),
                "Content-Type": "application/json",
            },
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "ok"


def test_browser_session_admin_can_register_provider(monkeypatch, tmp_path: Path) -> None:
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

    with create_server_test_client() as client:
        registered = client.post(
            "/api/auth/register",
            data={"email": "admin@example.com", "password": "password-1", "next": "/providers"},
            follow_redirects=False,
        )
        response = client.post("/api/providers", json=payload)

    assert registered.status_code == status.HTTP_303_SEE_OTHER
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok", "provider": "custom-api"}


def test_admin_can_update_custom_provider(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    create_payload = {
        "definition": {
            "name": "custom-api",
            "display_name": "Custom API",
            "auth_type": "api_key",
            "flow": "api_key",
            "api_url": "api.example.com",
            "api_key": {"header_name": "Authorization", "header_prefix": "Bearer"},
        }
    }
    update_payload = {
        "definition": {
            "name": "custom-api",
            "display_name": "Updated API",
            "auth_type": "api_key",
            "flow": "api_key",
            "api_url": "https://api.example.com/v2",
            "api_key": {"header_name": "x-api-key", "header_prefix": ""},
        }
    }
    create_body = json.dumps(create_payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    update_body = json.dumps(update_payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

    with create_server_test_client() as client:
        _register_identity(client, tmp_path, "steady-wisely-boldly-0042")
        created = client.post(
            "/api/providers",
            content=create_body,
            headers={
                **_auth_header(tmp_path, "POST", "/api/providers", body=create_body),
                "Content-Type": "application/json",
            },
        )
        response = client.put(
            "/api/providers/custom-api",
            content=update_body,
            headers={
                **_auth_header(tmp_path, "PUT", "/api/providers/custom-api", body=update_body),
                "Content-Type": "application/json",
            },
        )
        fetched = client.get(
            "/api/providers/custom-api",
            headers=_auth_header(tmp_path, "GET", "/api/providers/custom-api"),
        )

    assert created.status_code == status.HTTP_200_OK
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"status": "ok", "provider": "custom-api"}
    assert fetched.json()["display_name"] == "Updated API"
    assert fetched.json()["api_key"]["header_name"] == "x-api-key"


def test_provider_registration_rejects_invalid_url_fields(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    payload = {
        "definition": {
            "name": "custom-api",
            "display_name": "Custom API",
            "auth_type": "api_key",
            "flow": "api_key",
            "api_url": "https://api.example.com",
            "docs_url": "not a url",
            "api_key": {"header_name": "Authorization"},
        }
    }
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

    with create_server_test_client() as client:
        _register_identity(client, tmp_path, "steady-wisely-boldly-0042")
        response = client.post(
            "/api/providers",
            content=body,
            headers={
                **_auth_header(tmp_path, "POST", "/api/providers", body=body),
                "Content-Type": "application/json",
            },
        )
        fetched = client.get(
            "/api/providers/custom-api",
            headers=_auth_header(tmp_path, "GET", "/api/providers/custom-api"),
        )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "InvalidProviderSchemaError"
    assert "docs_url" in response.json()["message"]
    assert fetched.status_code == status.HTTP_404_NOT_FOUND
