import asyncio
import base64
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from authsome.auth.models.connection import ConnectionRecord
from authsome.auth.models.enums import AuthType, ConnectionStatus
from authsome.identity import create_identity, load_private_key
from authsome.identity.proof import create_proof_jwt
from authsome.server.app import create_app
from authsome.utils import build_store_key


def _auth_header(
    tmp_path: Path,
    method: str,
    path: str,
    body: bytes = b"",
    *,
    handle: str = "steady-wisely-boldly-0042",
    subject: str | None = None,
) -> dict[str, str]:
    identity = create_identity(tmp_path, handle)
    token = create_proof_jwt(
        private_key=load_private_key(tmp_path, identity.handle),
        issuer=identity.did,
        subject=subject or identity.handle,
        method=method,
        path_query=path,
        body=body,
    )
    return {"Authorization": f"PoP {token}"}


def test_whoami_requires_pop(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    with TestClient(create_app()) as client:
        response = client.get("/whoami")

    assert response.status_code == 401


def test_whoami_accepts_valid_pop_and_scopes_identity(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.setenv("AUTHSOME_MASTER_KEY", base64.b64encode(b"\x01" * 32).decode("ascii"))
    identity = create_identity(tmp_path, "steady-wisely-boldly-0042")

    with TestClient(create_app()) as client:
        register_response = client.post(
            "/identities/register",
            json={"handle": identity.handle, "did": identity.did},
        )
        assert register_response.status_code == 200
        response = client.get("/whoami", headers=_auth_header(tmp_path, "GET", "/whoami"))

    assert response.status_code == 200
    assert response.json()["identity"] == "steady-wisely-boldly-0042"
    assert response.json()["principal_id"].startswith("principal_")
    assert response.json()["vault_id"].startswith("vault_")
    assert response.json()["did"].startswith("did:key:z6Mk")
    assert response.json()["configured_encryption_mode"] == "auto"
    assert response.json()["effective_encryption_source"] == "env"
    assert "AUTHSOME_MASTER_KEY" in response.json()["encryption_backend"]


def test_health_and_ready_report_encryption_details(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.setenv("AUTHSOME_MASTER_KEY", base64.b64encode(b"\x02" * 32).decode("ascii"))
    identity = create_identity(tmp_path, "steady-wisely-boldly-0042")

    with TestClient(create_app()) as client:
        client.post("/identities/register", json={"handle": identity.handle, "did": identity.did})
        health_response = client.get("/health")
        ready_response = client.get("/ready", headers=_auth_header(tmp_path, "GET", "/ready"))

    assert health_response.status_code == 200
    assert health_response.json()["configured_encryption_mode"] == "auto"
    assert health_response.json()["effective_encryption_source"] == "env"
    assert "AUTHSOME_MASTER_KEY" in health_response.json()["encryption_backend"]
    assert ready_response.status_code == 200
    assert ready_response.json()["configured_encryption_mode"] == "auto"
    assert ready_response.json()["effective_encryption_source"] == "env"
    assert "AUTHSOME_MASTER_KEY" in ready_response.json()["encryption_backend"]


def test_rekey_rotates_local_vault(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    identity = create_identity(tmp_path, "steady-wisely-boldly-0042")

    with TestClient(create_app()) as client:
        client.post("/identities/register", json={"handle": identity.handle, "did": identity.did})
        resolved = asyncio.run(client.app.state.ownership_resolver.resolve(identity=identity.handle))
        asyncio.run(client.app.state.vault.put("key1", "secret-value-1", collection=f"vault:{resolved.vault_id}"))

        response = client.post("/rekey", json={}, headers=_auth_header(tmp_path, "POST", "/rekey", b"{}"))

        assert response.status_code == 200
        assert response.json()["status"] == "ok"
        assert (
            asyncio.run(client.app.state.vault.get("key1", collection=f"vault:{resolved.vault_id}")) == "secret-value-1"
        )


def test_rekey_rejects_env_master_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.setenv("AUTHSOME_MASTER_KEY", base64.b64encode(b"\x03" * 32).decode("ascii"))
    identity = create_identity(tmp_path, "steady-wisely-boldly-0042")

    with TestClient(create_app()) as client:
        client.post("/identities/register", json={"handle": identity.handle, "did": identity.did})
        response = client.post("/rekey", json={}, headers=_auth_header(tmp_path, "POST", "/rekey", b"{}"))

    assert response.status_code == 400
    assert "AUTHSOME_MASTER_KEY" in response.json()["detail"]


def test_hosted_registration_requires_claim(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.setenv("AUTHSOME_DEPLOYMENT_MODE", "hosted")
    identity = create_identity(tmp_path, "steady-wisely-boldly-0042")

    with TestClient(create_app()) as client:
        response = client.post("/identities/register", json={"handle": identity.handle, "did": identity.did})

    assert response.status_code == 200
    assert response.json()["registration_status"] == "claim_required"
    assert "/ui/claim/" in response.json()["claim_url"]


def test_whoami_rejects_wrong_path_claim(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    identity = create_identity(tmp_path, "steady-wisely-boldly-0042")

    with TestClient(create_app()) as client:
        client.post("/identities/register", json={"handle": identity.handle, "did": identity.did})
        response = client.get("/whoami", headers=_auth_header(tmp_path, "GET", "/connections"))

    assert response.status_code == 401


def test_whoami_rejects_unknown_subject(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    with TestClient(create_app()) as client:
        response = client.get("/whoami", headers=_auth_header(tmp_path, "GET", "/whoami"))

    assert response.status_code == 401


def test_whoami_rejects_registered_handle_with_wrong_issuer(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    victim = create_identity(tmp_path, "steady-wisely-boldly-0042")
    attacker = create_identity(tmp_path, "rapid-brightly-firmly-0007")

    with TestClient(create_app()) as client:
        client.post("/identities/register", json={"handle": victim.handle, "did": victim.did})
        client.post("/identities/register", json={"handle": attacker.handle, "did": attacker.did})
        response = client.get(
            "/whoami",
            headers=_auth_header(
                tmp_path,
                "GET",
                "/whoami",
                handle=attacker.handle,
                subject=victim.handle,
            ),
        )

    assert response.status_code == 401


def test_identity_registration_rejects_duplicate_handle_different_did(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    first = create_identity(tmp_path, "steady-wisely-boldly-0042")
    second = create_identity(tmp_path, "rapid-brightly-firmly-0007")

    with TestClient(create_app()) as client:
        assert client.post("/identities/register", json={"handle": first.handle, "did": first.did}).status_code == 200
        response = client.post("/identities/register", json={"handle": first.handle, "did": second.did})

    assert response.status_code == 409


def test_identity_registration_rejects_duplicate_did_different_handle(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    identity = create_identity(tmp_path, "steady-wisely-boldly-0042")

    with TestClient(create_app()) as client:
        assert (
            client.post("/identities/register", json={"handle": identity.handle, "did": identity.did}).status_code
            == 200
        )
        response = client.post(
            "/identities/register",
            json={"handle": "rapid-brightly-firmly-0007", "did": identity.did},
        )

    assert response.status_code == 409


def test_ready_uses_active_identity_connections_for_warning_check(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    identity = create_identity(tmp_path, "steady-wisely-boldly-0042")

    with TestClient(create_app()) as client:
        client.post("/identities/register", json={"handle": identity.handle, "did": identity.did})
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

        response = client.get("/ready", headers=_auth_header(tmp_path, "GET", "/ready"))

    assert response.status_code == 200
    assert response.json()["checks"]["connections"] == "ok"
    assert "no active provider connections found" not in response.json()["warnings"]
