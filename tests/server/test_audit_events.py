import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from authsome.audit import AuditEvent, emit, emit_event
from authsome.cli.identity import RuntimeIdentity
from authsome.server.store import create_server_store
from tests.server.helpers import create_server_test_client
from tests.server.test_pop_auth import _auth_header


def _claim_identity(client: TestClient, tmp_path: Path, handle: str, *, email: str) -> None:
    identity = RuntimeIdentity.create(tmp_path, handle)
    response = client.post("/api/identities/register", json={"handle": identity.handle, "did": identity.did})
    assert response.status_code == status.HTTP_200_OK
    claim_url = urlparse(response.json()["claim_url"])
    token = parse_qs(claim_url.query)["token"][0]
    claim_path = f"/api/claim/{token}"
    registered = client.post(
        "/api/auth/register",
        data={"email": email, "password": "password-1", "next": claim_path},
        follow_redirects=False,
    )
    assert registered.status_code == status.HTTP_303_SEE_OTHER
    assert client.post(f"{claim_path}/confirm", follow_redirects=False).status_code == status.HTTP_303_SEE_OTHER


def _emit_audit_event(  # noqa: PLR0913
    event_id: str,
    event: str,
    *,
    principal_id: str | None,
    identity: str | None,
    provider: str | None = None,
    connection: str | None = None,
    status: str | None = "success",
    timestamp: datetime | None = None,
) -> None:
    emit(
        AuditEvent(
            event_id=event_id,
            timestamp=timestamp or datetime(2099, 1, 1, 8, 0, tzinfo=UTC),
            event=event,
            principal_id=principal_id,
            identity=identity,
            provider=provider,
            connection=connection,
            status=status,
        )
    )


def test_audit_events_endpoint_returns_internal_events_for_admin(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    with create_server_test_client() as client:
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

    assert response.status_code == status.HTTP_200_OK
    entries = response.json()["entries"]
    assert entries[0]["event"] == "login"
    assert entries[0]["identity"] == "steady-wisely-boldly-0042"
    assert entries[0]["principal_id"] == whoami["principal_id"]
    assert entries[0]["provider"] == "github"


def test_audit_events_endpoint_only_documents_pagination_params(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    with create_server_test_client() as client:
        response = client.get("/openapi.json")

    assert response.status_code == status.HTTP_200_OK
    params = response.json()["paths"]["/api/audit/events"]["get"]["parameters"]
    assert {param["name"] for param in params} == {"limit", "cursor", "identity"}


def test_external_audit_post_is_enriched_from_pop_identity(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    payload = {"event": {"event": "proxy_deny", "metadata": {"host": "api.example.com", "reason": "no_match"}}}
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

    with create_server_test_client() as client:
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

    assert posted.status_code == status.HTTP_200_OK
    entries = response.json()["entries"]
    assert entries[0]["event"] == "proxy_deny"
    assert entries[0]["source"] == "external"
    assert entries[0]["identity"] == "steady-wisely-boldly-0042"
    assert entries[0]["principal_id"].startswith("principal_")
    assert entries[0]["host"] == "api.example.com"
    assert entries[0]["reason"] == "no_match"


def test_admin_sees_all_audit_events_and_user_sees_only_own_principal(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    with create_server_test_client() as client:
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

    assert admin_response.status_code == status.HTTP_200_OK
    admin_events = {entry["event"] for entry in admin_response.json()["entries"]}
    assert {"admin_event", "user_event"}.issubset(admin_events)

    assert user_response.status_code == status.HTTP_200_OK
    user_entries = user_response.json()["entries"]
    assert "user_event" in {entry["event"] for entry in user_entries}
    assert "admin_event" not in {entry["event"] for entry in user_entries}
    assert all(entry["principal_id"] == user_whoami["principal_id"] for entry in user_entries)


def test_non_admin_audit_query_params_do_not_filter_or_widen_scope(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    with create_server_test_client() as client:
        _claim_identity(client, tmp_path, "admin-ready-boldly-0001", email="admin@example.com")
        _claim_identity(client, tmp_path, "steady-wisely-boldly-0042", email="user@example.com")
        admin_whoami = client.get(
            "/api/whoami",
            headers=_auth_header(tmp_path, "GET", "/api/whoami", handle="admin-ready-boldly-0001"),
        ).json()
        user_whoami = client.get(
            "/api/whoami",
            headers=_auth_header(tmp_path, "GET", "/api/whoami", handle="steady-wisely-boldly-0042"),
        ).json()
        _emit_audit_event(
            "audit_001",
            "connection.login",
            principal_id=admin_whoami["principal_id"],
            identity="admin-ready-boldly-0001",
            provider="github",
        )
        _emit_audit_event(
            "audit_002",
            "connection.login",
            principal_id=user_whoami["principal_id"],
            identity="steady-wisely-boldly-0042",
            provider="github",
        )
        _emit_audit_event(
            "audit_003",
            "connection.logout",
            principal_id=user_whoami["principal_id"],
            identity="steady-wisely-boldly-0042",
            provider="linear",
        )

        response = client.get(
            "/api/audit/events?provider=github&limit=10",
            headers=_auth_header(
                tmp_path,
                "GET",
                "/api/audit/events?provider=github&limit=10",
                handle="steady-wisely-boldly-0042",
            ),
        )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["scope"] == "principal"
    manual_entries = [entry for entry in body["entries"] if entry["event_id"].startswith("audit_00")]
    assert [entry["event_id"] for entry in manual_entries] == ["audit_003", "audit_002"]
    assert all(entry["principal_id"] == user_whoami["principal_id"] for entry in body["entries"])


def test_non_admin_audit_query_cannot_widen_scope_with_principal_or_identity(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    with create_server_test_client() as client:
        _claim_identity(client, tmp_path, "admin-ready-boldly-0001", email="admin@example.com")
        _claim_identity(client, tmp_path, "steady-wisely-boldly-0042", email="user@example.com")
        admin_whoami = client.get(
            "/api/whoami",
            headers=_auth_header(tmp_path, "GET", "/api/whoami", handle="admin-ready-boldly-0001"),
        ).json()
        user_whoami = client.get(
            "/api/whoami",
            headers=_auth_header(tmp_path, "GET", "/api/whoami", handle="steady-wisely-boldly-0042"),
        ).json()
        _emit_audit_event(
            "audit_010",
            "connection.login",
            principal_id=admin_whoami["principal_id"],
            identity="admin-ready-boldly-0001",
            provider="github",
        )
        _emit_audit_event(
            "audit_011",
            "connection.login",
            principal_id=user_whoami["principal_id"],
            identity="steady-wisely-boldly-0042",
            provider="github",
        )

        path = (
            f"/api/audit/events?principal_id={admin_whoami['principal_id']}&identity=admin-ready-boldly-0001&limit=10"
        )
        response = client.get(
            path,
            headers=_auth_header(
                tmp_path,
                "GET",
                path,
                handle="steady-wisely-boldly-0042",
            ),
        )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["scope"] == "principal"
    event_ids = {entry["event_id"] for entry in body["entries"]}
    assert "audit_010" not in event_ids
    assert all(entry["principal_id"] == user_whoami["principal_id"] for entry in body["entries"])


def test_audit_events_can_filter_current_principal_by_identity(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    with create_server_test_client() as client:
        _claim_identity(client, tmp_path, "steady-wisely-boldly-0042", email="user@example.com")
        _claim_identity(client, tmp_path, "calmly-simply-boldly-0043", email="user@example.com")
        whoami = client.get(
            "/api/whoami",
            headers=_auth_header(tmp_path, "GET", "/api/whoami", handle="steady-wisely-boldly-0042"),
        ).json()
        _emit_audit_event(
            "audit_020",
            "connection.login",
            principal_id=whoami["principal_id"],
            identity="steady-wisely-boldly-0042",
            provider="github",
        )
        _emit_audit_event(
            "audit_021",
            "connection.logout",
            principal_id=whoami["principal_id"],
            identity="calmly-simply-boldly-0043",
            provider="linear",
        )
        path = "/api/audit/events?identity=calmly-simply-boldly-0043&limit=10"
        response = client.get(
            path,
            headers=_auth_header(tmp_path, "GET", path, handle="steady-wisely-boldly-0042"),
        )

    assert response.status_code == status.HTTP_200_OK
    manual_entries = [entry for entry in response.json()["entries"] if entry["event_id"].startswith("audit_02")]
    assert [entry["event_id"] for entry in manual_entries] == ["audit_021"]


def test_admin_audit_events_support_cursor_pagination(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    with create_server_test_client() as client:
        _claim_identity(client, tmp_path, "admin-ready-boldly-0001", email="admin@example.com")
        _claim_identity(client, tmp_path, "steady-wisely-boldly-0042", email="user@example.com")
        admin_whoami = client.get(
            "/api/whoami",
            headers=_auth_header(tmp_path, "GET", "/api/whoami", handle="admin-ready-boldly-0001"),
        ).json()
        user_whoami = client.get(
            "/api/whoami",
            headers=_auth_header(tmp_path, "GET", "/api/whoami", handle="steady-wisely-boldly-0042"),
        ).json()
        _emit_audit_event(
            "audit_100",
            "connection.login",
            principal_id=admin_whoami["principal_id"],
            identity="admin-ready-boldly-0001",
            provider="github",
            timestamp=datetime(2099, 1, 1, 8, 0, tzinfo=UTC),
        )
        _emit_audit_event(
            "audit_099",
            "connection.logout",
            principal_id=admin_whoami["principal_id"],
            identity="admin-ready-boldly-0001",
            provider="linear",
            timestamp=datetime(2099, 1, 1, 7, 59, tzinfo=UTC),
        )
        _emit_audit_event(
            "audit_101",
            "connection.login",
            principal_id=user_whoami["principal_id"],
            identity="steady-wisely-boldly-0042",
            provider="github",
            timestamp=datetime(2099, 1, 1, 8, 1, tzinfo=UTC),
        )
        _emit_audit_event(
            "audit_102",
            "connection.logout",
            principal_id=user_whoami["principal_id"],
            identity="steady-wisely-boldly-0042",
            provider="github",
            timestamp=datetime(2099, 1, 1, 8, 2, tzinfo=UTC),
        )

        first_path = "/api/audit/events?limit=2"
        first_response = client.get(
            first_path,
            headers=_auth_header(
                tmp_path,
                "GET",
                first_path,
                handle="admin-ready-boldly-0001",
            ),
        )
        assert first_response.status_code == status.HTTP_200_OK
        first_body = first_response.json()
        second_path = f"/api/audit/events?limit=2&cursor={first_body['next_cursor']}"
        second_response = client.get(
            second_path,
            headers=_auth_header(
                tmp_path,
                "GET",
                second_path,
                handle="admin-ready-boldly-0001",
            ),
        )

    assert first_body["scope"] == "global"
    assert [entry["event_id"] for entry in first_body["entries"]] == ["audit_102", "audit_101"]
    assert first_body["next_cursor"]

    assert second_response.status_code == status.HTTP_200_OK
    second_body = second_response.json()
    assert second_body["scope"] == "global"
    assert [entry["event_id"] for entry in second_body["entries"]] == ["audit_100", "audit_099"]


@pytest.mark.asyncio
async def test_audit_log_async_shutdown_flushes_events_without_blocking_loop(tmp_path: Path) -> None:
    store = await create_server_store(home=tmp_path)
    audit_log = store.audit_events.configure_exporter()
    try:
        emit_event("shutdown.flush", identity="agent-a", principal_id="principal_a", provider="github")

        await asyncio.wait_for(audit_log.async_shutdown(), timeout=1)

        entries = await store.audit_events.list_recent(limit=10, principal_id="principal_a")
    finally:
        await store.close()

    assert [entry["event"] for entry in entries] == ["shutdown.flush"]
