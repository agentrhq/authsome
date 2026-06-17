import asyncio
import base64
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from fastapi import status
from fastapi.testclient import TestClient

from authsome.auth.models.connection import ConnectionRecord
from authsome.auth.models.enums import AuthType, ConnectionStatus
from authsome.cli.identity import RuntimeIdentity
from authsome.identity.proof import create_proof_jwt
from authsome.server.credential_repository import build_store_key
from tests.server.helpers import create_server_test_client


def _auth_header(  # noqa: PLR0913
    tmp_path: Path,
    method: str,
    path: str,
    body: bytes = b"",
    *,
    handle: str = "steady-wisely-boldly-0042",
    subject: str | None = None,
) -> dict[str, str]:
    identity = RuntimeIdentity.create(tmp_path, handle)
    token = create_proof_jwt(
        private_key=RuntimeIdentity.load_private_key(tmp_path, identity.handle),
        issuer=identity.did,
        subject=subject or identity.handle,
        method=method,
        path_query=path,
        body=body,
    )
    return {"Authorization": f"PoP {token}"}


def register_and_claim_identity(
    client: TestClient,
    tmp_path: Path,
    handle: str = "steady-wisely-boldly-0042",
    *,
    email: str = "dev@example.com",
) -> None:
    """Register an identity and drive the browser claim flow through to acceptance."""
    identity = RuntimeIdentity.create(tmp_path, handle)
    response = client.post("/api/identities/register", json={"handle": identity.handle, "did": identity.did})
    assert response.status_code == status.HTTP_200_OK
    claim_url = urlparse(response.json()["claim_url"])
    token = parse_qs(claim_url.query)["token"][0]
    claim_path = f"/api/claim/{token}"
    assert client.get(claim_path).status_code == status.HTTP_200_OK
    registered = client.post(
        "/api/auth/register",
        data={"email": email, "password": "password-1", "next": claim_path},
        follow_redirects=False,
    )
    assert registered.status_code == status.HTTP_303_SEE_OTHER
    assert client.post(f"{claim_path}/confirm", follow_redirects=False).status_code == status.HTTP_303_SEE_OTHER


def test_whoami_requires_pop(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    with create_server_test_client() as client:
        response = client.get("/api/whoami")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_whoami_accepts_valid_pop_and_scopes_identity(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.setenv("AUTHSOME_MASTER_KEY", base64.b64encode(b"\x01" * 32).decode("ascii"))
    with create_server_test_client() as client:
        register_and_claim_identity(client, tmp_path, "steady-wisely-boldly-0042")
        response = client.get("/api/whoami", headers=_auth_header(tmp_path, "GET", "/api/whoami"))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["identity"] == "steady-wisely-boldly-0042"
    assert response.json()["principal_id"].startswith("principal_")
    assert response.json()["vault_id"].startswith("vault_")
    assert response.json()["did"].startswith("did:key:z6Mk")
    assert response.json()["configured_encryption_mode"] == "aes-256-gcm"
    assert response.json()["effective_encryption_source"] == "aes-256-gcm"
    assert "Argon2id" in response.json()["encryption_backend"]


def test_whoami_rejects_replayed_pop_jwt(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.setenv("AUTHSOME_MASTER_KEY", base64.b64encode(b"\x03" * 32).decode("ascii"))

    with create_server_test_client() as client:
        register_and_claim_identity(client, tmp_path, "steady-wisely-boldly-0042")
        headers = _auth_header(tmp_path, "GET", "/api/whoami")

        first_response = client.get("/api/whoami", headers=headers)
        second_response = client.get("/api/whoami", headers=headers)

    assert first_response.status_code == status.HTTP_200_OK
    assert second_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert second_response.json()["detail"] == "Proof JWT was already used"


def test_health_and_ready_report_encryption_details(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.setenv("AUTHSOME_MASTER_KEY", base64.b64encode(b"\x02" * 32).decode("ascii"))

    with create_server_test_client() as client:
        register_and_claim_identity(client, tmp_path, "steady-wisely-boldly-0042")
        health_response = client.get("/api/health")
        ready_response = client.get("/api/ready", headers=_auth_header(tmp_path, "GET", "/api/ready"))

    assert health_response.status_code == status.HTTP_200_OK
    assert health_response.json()["configured_encryption_mode"] == "aes-256-gcm"
    assert health_response.json()["effective_encryption_source"] == "aes-256-gcm"
    assert "Argon2id" in health_response.json()["encryption_backend"]
    assert ready_response.status_code == status.HTTP_200_OK
    assert ready_response.json()["configured_encryption_mode"] == "aes-256-gcm"
    assert ready_response.json()["effective_encryption_source"] == "aes-256-gcm"
    assert "Argon2id" in ready_response.json()["encryption_backend"]


def test_registration_requires_claim(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    identity = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")

    with create_server_test_client() as client:
        response = client.post("/api/identities/register", json={"handle": identity.handle, "did": identity.did})

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["registration_status"] == "claim_required"
    assert "/claim?" in response.json()["claim_url"]


def test_resolve_identity_by_did_returns_handle(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    identity = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")

    with create_server_test_client() as client:
        client.post("/api/identities/register", json={"handle": identity.handle, "did": identity.did})
        response = client.get(f"/api/identities/by-did/{identity.did}")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["identity"] == identity.handle
    assert response.json()["did"] == identity.did


def test_identity_detail_returns_owner_status_and_active_flag(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    identity = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")

    with create_server_test_client() as client:
        register_and_claim_identity(client, tmp_path, identity.handle)
        response = client.get(
            f"/api/identities/{identity.handle}/detail",
            headers=_auth_header(tmp_path, "GET", f"/api/identities/{identity.handle}/detail"),
        )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["handle"] == identity.handle
    assert body["did"] == identity.did
    assert body["claim_status"] == "accepted"
    assert body["principal_id"].startswith("principal_")
    assert body["is_active"] is True
    assert body["created_at"]


def test_resolve_identity_by_did_returns_404_for_unknown_did(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    identity = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")

    with create_server_test_client() as client:
        response = client.get(f"/api/identities/by-did/{identity.did}")

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_whoami_rejects_wrong_path_claim(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    identity = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")

    with create_server_test_client() as client:
        client.post("/api/identities/register", json={"handle": identity.handle, "did": identity.did})
        response = client.get("/api/whoami", headers=_auth_header(tmp_path, "GET", "/api/connections"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_whoami_rejects_unknown_subject(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    with create_server_test_client() as client:
        response = client.get("/api/whoami", headers=_auth_header(tmp_path, "GET", "/api/whoami"))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_whoami_rejects_registered_handle_with_wrong_issuer(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    victim = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")
    attacker = RuntimeIdentity.create(tmp_path, "rapid-brightly-firmly-0007")

    with create_server_test_client() as client:
        client.post("/api/identities/register", json={"handle": victim.handle, "did": victim.did})
        client.post("/api/identities/register", json={"handle": attacker.handle, "did": attacker.did})
        response = client.get(
            "/api/whoami",
            headers=_auth_header(
                tmp_path,
                "GET",
                "/api/whoami",
                handle=attacker.handle,
                subject=victim.handle,
            ),
        )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_identity_registration_rejects_duplicate_handle_different_did(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    first = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")
    second = RuntimeIdentity.create(tmp_path, "rapid-brightly-firmly-0007")

    with create_server_test_client() as client:
        assert (
            client.post("/api/identities/register", json={"handle": first.handle, "did": first.did}).status_code
            == status.HTTP_200_OK
        )
        response = client.post("/api/identities/register", json={"handle": first.handle, "did": second.did})

    assert response.status_code == status.HTTP_409_CONFLICT


def test_identity_registration_rejects_duplicate_did_different_handle(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    identity = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")

    with create_server_test_client() as client:
        assert (
            client.post("/api/identities/register", json={"handle": identity.handle, "did": identity.did}).status_code
            == status.HTTP_200_OK
        )
        response = client.post(
            "/api/identities/register",
            json={"handle": "rapid-brightly-firmly-0007", "did": identity.did},
        )

    assert response.status_code == status.HTTP_409_CONFLICT


def test_ready_uses_active_identity_connections_for_warning_check(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    identity = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")

    with create_server_test_client() as client:
        register_and_claim_identity(client, tmp_path, identity.handle)
        resolved = asyncio.run(client.app.state.ownership_resolver.resolve(identity=identity.handle))
        key = build_store_key(
            vault=resolved.vault_id,
            provider="github",
            record_type="connection",
            connection="default",
        )
        record = ConnectionRecord(
            provider="github",
            identity=identity.handle,
            connection_name="default",
            auth_type=AuthType.OAUTH2,
            status=ConnectionStatus.CONNECTED,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        asyncio.run(client.app.state.vault.put(key, record.model_dump_json(), collection=f"vault:{resolved.vault_id}"))

        response = client.get("/api/ready", headers=_auth_header(tmp_path, "GET", "/api/ready"))

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["checks"]["connections"] == "ok"
    assert "no active provider connections found" not in response.json()["warnings"]
