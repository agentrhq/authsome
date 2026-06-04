from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from authsome.audit import emit_event
from authsome.cli.identity import create_identity
from authsome.server.app import create_app
from tests.server.test_pop_auth import _auth_header


def _claim_identity(client: TestClient, tmp_path: Path, handle: str, *, email: str) -> None:
    identity = create_identity(tmp_path, handle)
    response = client.post("/api/identities/register", json={"handle": identity.handle, "did": identity.did})
    assert response.status_code == 200
    claim_url = urlparse(response.json()["claim_url"])
    token = parse_qs(claim_url.query)["token"][0]
    claim_path = f"/api/claim/{token}"
    registered = client.post(
        "/api/auth/register",
        data={"email": email, "password": "password-1", "next": claim_path},
        follow_redirects=False,
    )
    assert registered.status_code == 303
    assert client.post(f"{claim_path}/confirm", follow_redirects=False).status_code == 303


def test_audit_events_endpoint_returns_internal_events_for_admin(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    with TestClient(create_app()) as client:
        _claim_identity(client, tmp_path, "steady-wisely-boldly-0042", email="dev@example.com")
        whoami = client.get("/api/whoami", headers=_auth_header(tmp_path, "GET", "/api/whoami")).json()
        emit_event(
            "login",
            identity="steady-wisely-boldly-0042",
            principal_id=whoami["principal_id"],
            provider="github",
        )

        response = client.get(
            "/api/audit/events?limit=10",
            headers=_auth_header(tmp_path, "GET", "/api/audit/events?limit=10"),
        )

    assert response.status_code == 200
    entries = response.json()["entries"]
    assert entries[0]["event"] == "login"
    assert entries[0]["identity"] == "steady-wisely-boldly-0042"
    assert entries[0]["principal_id"] == whoami["principal_id"]
    assert entries[0]["provider"] == "github"


def test_external_audit_post_is_enriched_from_pop_identity(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    payload = {"event": {"event": "proxy_deny", "metadata": {"host": "api.example.com", "reason": "no_match"}}}
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

    with TestClient(create_app()) as client:
        _claim_identity(client, tmp_path, "steady-wisely-boldly-0042", email="dev@example.com")
        posted = client.post(
            "/api/audit/events",
            content=body,
            headers={
                **_auth_header(tmp_path, "POST", "/api/audit/events", body=body),
                "Content-Type": "application/json",
            },
        )
        response = client.get(
            "/api/audit/events?limit=10",
            headers=_auth_header(tmp_path, "GET", "/api/audit/events?limit=10"),
        )

    assert posted.status_code == 200
    entries = response.json()["entries"]
    assert entries[0]["event"] == "proxy_deny"
    assert entries[0]["source"] == "external"
    assert entries[0]["identity"] == "steady-wisely-boldly-0042"
    assert entries[0]["principal_id"].startswith("principal_")
    assert entries[0]["host"] == "api.example.com"
    assert entries[0]["reason"] == "no_match"


def test_admin_sees_all_audit_events_and_user_sees_only_own_principal(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    with TestClient(create_app()) as client:
        _claim_identity(client, tmp_path, "admin-ready-boldly-0001", email="admin@example.com")
        _claim_identity(client, tmp_path, "steady-wisely-boldly-0042", email="user@example.com")
        admin_whoami = client.get(
            "/api/whoami",
            headers=_auth_header(tmp_path, "GET", "/api/whoami", handle="admin-ready-boldly-0001"),
        ).json()
        user_whoami = client.get("/api/whoami", headers=_auth_header(tmp_path, "GET", "/api/whoami")).json()
        emit_event(
            "admin_event",
            identity="admin-ready-boldly-0001",
            principal_id=admin_whoami["principal_id"],
            provider="github",
        )
        emit_event(
            "user_event",
            identity="steady-wisely-boldly-0042",
            principal_id=user_whoami["principal_id"],
            provider="linear",
        )

        admin_response = client.get(
            "/api/audit/events?limit=20",
            headers=_auth_header(tmp_path, "GET", "/api/audit/events?limit=20", handle="admin-ready-boldly-0001"),
        )
        user_response = client.get(
            "/api/audit/events",
            headers=_auth_header(tmp_path, "GET", "/api/audit/events"),
        )

    assert admin_response.status_code == 200
    admin_events = {entry["event"] for entry in admin_response.json()["entries"]}
    assert {"admin_event", "user_event"}.issubset(admin_events)

    assert user_response.status_code == 200
    user_entries = user_response.json()["entries"]
    assert "user_event" in {entry["event"] for entry in user_entries}
    assert "admin_event" not in {entry["event"] for entry in user_entries}
    assert all(entry["principal_id"] == user_whoami["principal_id"] for entry in user_entries)
