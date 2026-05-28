from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from fastapi.testclient import TestClient

from authsome.audit import emit_event
from authsome.identity import create_identity
from authsome.server.app import create_app
from tests.server.test_pop_auth import _auth_header


def _register_identity(client: TestClient, tmp_path: Path, handle: str) -> None:
    identity = create_identity(tmp_path, handle)
    response = client.post("/identities/register", json={"handle": identity.handle, "did": identity.did})
    assert response.status_code == 200


def _claim_identity(client: TestClient, tmp_path: Path, handle: str, *, email: str) -> None:
    identity = create_identity(tmp_path, handle)
    response = client.post("/identities/register", json={"handle": identity.handle, "did": identity.did})
    assert response.status_code == 200
    claim_path = urlparse(response.json()["claim_url"]).path
    registered = client.post(
        "/auth/register",
        data={"email": email, "password": "password-1", "next": claim_path},
        follow_redirects=False,
    )
    assert registered.status_code == 303
    assert client.post(f"{claim_path}/confirm", follow_redirects=False).status_code == 303


def test_audit_events_endpoint_returns_internal_events_for_admin(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.delenv("AUTHSOME_DEPLOYMENT_MODE", raising=False)

    with TestClient(create_app()) as client:
        _register_identity(client, tmp_path, "steady-wisely-boldly-0042")
        whoami = client.get("/whoami", headers=_auth_header(tmp_path, "GET", "/whoami")).json()
        emit_event(
            "login",
            identity="steady-wisely-boldly-0042",
            principal_id=whoami["principal_id"],
            provider="github",
        )

        response = client.get(
            "/audit/events?limit=10",
            headers=_auth_header(tmp_path, "GET", "/audit/events?limit=10"),
        )

    assert response.status_code == 200
    entries = response.json()["entries"]
    assert entries[0]["event"] == "login"
    assert entries[0]["identity"] == "steady-wisely-boldly-0042"
    assert entries[0]["principal_id"] == whoami["principal_id"]
    assert entries[0]["provider"] == "github"


def test_external_audit_post_is_enriched_from_pop_identity(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.delenv("AUTHSOME_DEPLOYMENT_MODE", raising=False)
    payload = {"event": {"event": "proxy_deny", "metadata": {"host": "api.example.com", "reason": "no_match"}}}
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

    with TestClient(create_app()) as client:
        _register_identity(client, tmp_path, "steady-wisely-boldly-0042")
        posted = client.post(
            "/audit/events",
            content=body,
            headers={
                **_auth_header(tmp_path, "POST", "/audit/events", body=body),
                "Content-Type": "application/json",
            },
        )
        response = client.get(
            "/audit/events?limit=10",
            headers=_auth_header(tmp_path, "GET", "/audit/events?limit=10"),
        )

    assert posted.status_code == 200
    entries = response.json()["entries"]
    assert entries[0]["event"] == "proxy_deny"
    assert entries[0]["source"] == "external"
    assert entries[0]["identity"] == "steady-wisely-boldly-0042"
    assert entries[0]["principal_id"].startswith("principal_")
    assert entries[0]["host"] == "api.example.com"
    assert entries[0]["reason"] == "no_match"


def test_hosted_user_cannot_query_audit_events(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.setenv("AUTHSOME_DEPLOYMENT_MODE", "hosted")

    with TestClient(create_app()) as client:
        _claim_identity(client, tmp_path, "admin-ready-boldly-0001", email="admin@example.com")
        _claim_identity(client, tmp_path, "steady-wisely-boldly-0042", email="user@example.com")
        response = client.get(
            "/audit/events",
            headers=_auth_header(tmp_path, "GET", "/audit/events"),
        )

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin role required"
