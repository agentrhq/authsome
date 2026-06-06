"""Session ownership tests for protected auth routes."""

import asyncio
from pathlib import Path

from fastapi import status
from fastapi.testclient import TestClient

from authsome.auth.models.enums import FlowType
from authsome.cli.identity import RuntimeIdentity
from authsome.identity.proof import create_proof_jwt
from authsome.server.app import create_app
from tests.server.test_pop_auth import TEST_SERVER_BASE_URL, register_and_claim_identity


def _auth_header(
    tmp_path: Path,
    method: str,
    path: str,
    *,
    handle: str,
) -> dict[str, str]:
    identity = RuntimeIdentity.create(tmp_path, handle)
    token = create_proof_jwt(
        private_key=RuntimeIdentity.load_private_key(tmp_path, identity.handle),
        issuer=identity.did,
        subject=identity.handle,
        method=method,
        path_query=path,
        body=b"",
    )
    return {"Authorization": f"PoP {token}"}


def test_get_session_rejects_other_identity(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    owner = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")
    stranger = RuntimeIdentity.create(tmp_path, "rapid-brightly-firmly-0007")
    app = create_app()

    with TestClient(app, base_url=TEST_SERVER_BASE_URL) as client:
        owner_registration = client.post("/api/identities/register", json={"handle": owner.handle, "did": owner.did})
        assert owner_registration.status_code == status.HTTP_200_OK
        register_and_claim_identity(client, tmp_path, stranger.handle, email="stranger@example.com")
        session = asyncio.run(
            client.app.state.auth_sessions.create(
                provider="github",
                identity=owner.handle,
                principal_id="principal_1",
                connection_name="default",
                flow_type=FlowType.PKCE.value,
            )
        )

        response = client.get(
            f"/api/auth/sessions/{session.session_id}",
            headers=_auth_header(
                tmp_path,
                "GET",
                f"/api/auth/sessions/{session.session_id}",
                handle=stranger.handle,
            ),
        )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Authentication session not found"


def test_resume_session_rejects_other_identity(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    owner = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")
    stranger = RuntimeIdentity.create(tmp_path, "rapid-brightly-firmly-0007")
    app = create_app()

    with TestClient(app, base_url=TEST_SERVER_BASE_URL) as client:
        owner_registration = client.post("/api/identities/register", json={"handle": owner.handle, "did": owner.did})
        assert owner_registration.status_code == status.HTTP_200_OK
        stranger_registration = client.post(
            "/api/identities/register",
            json={"handle": stranger.handle, "did": stranger.did},
        )
        assert stranger_registration.status_code == status.HTTP_200_OK
        session = asyncio.run(
            client.app.state.auth_sessions.create(
                provider="github",
                identity=owner.handle,
                principal_id="principal_1",
                connection_name="default",
                flow_type=FlowType.PKCE.value,
            )
        )

        response = client.post(
            f"/api/auth/sessions/{session.session_id}/resume",
            json={"data": {}},
            headers=_auth_header(
                tmp_path,
                "POST",
                f"/api/auth/sessions/{session.session_id}/resume",
                handle=stranger.handle,
            ),
        )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json()["detail"] == "Proof JWT body hash does not match request"


def test_sessions_do_not_survive_app_recreation(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    owner = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")
    session_id = ""

    with TestClient(create_app(), base_url=TEST_SERVER_BASE_URL) as first_client:
        register_and_claim_identity(first_client, tmp_path, owner.handle)
        session = asyncio.run(
            first_client.app.state.auth_sessions.create(
                provider="github",
                identity=owner.handle,
                principal_id="principal_1",
                connection_name="default",
                flow_type=FlowType.PKCE.value,
            )
        )
        session_id = session.session_id

    with TestClient(create_app(), base_url=TEST_SERVER_BASE_URL) as second_client:
        response = second_client.get(
            f"/api/auth/sessions/{session_id}",
            headers=_auth_header(tmp_path, "GET", f"/api/auth/sessions/{session_id}", handle=owner.handle),
        )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Authentication session not found"
