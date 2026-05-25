"""Session ownership tests for protected auth routes."""

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from authsome.auth.models.enums import FlowType
from authsome.identity import create_identity
from authsome.identity.proof import create_proof_jwt
from authsome.server.app import create_app


def _auth_header(
    tmp_path: Path,
    method: str,
    path: str,
    *,
    handle: str,
) -> dict[str, str]:
    from authsome.identity import load_private_key

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


def test_get_session_rejects_other_identity(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.delenv("AUTHSOME_DEPLOYMENT_MODE", raising=False)
    owner = create_identity(tmp_path, "steady-wisely-boldly-0042")
    stranger = create_identity(tmp_path, "rapid-brightly-firmly-0007")
    app = create_app()

    with TestClient(app) as client:
        owner_registration = client.post("/identities/register", json={"handle": owner.handle, "did": owner.did})
        assert owner_registration.status_code == 200
        stranger_registration = client.post(
            "/identities/register",
            json={"handle": stranger.handle, "did": stranger.did},
        )
        assert stranger_registration.status_code == 200
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
            f"/auth/sessions/{session.session_id}",
            headers=_auth_header(
                tmp_path,
                "GET",
                f"/auth/sessions/{session.session_id}",
                handle=stranger.handle,
            ),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Authentication session not found"


def test_resume_session_rejects_other_identity(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.delenv("AUTHSOME_DEPLOYMENT_MODE", raising=False)
    owner = create_identity(tmp_path, "steady-wisely-boldly-0042")
    stranger = create_identity(tmp_path, "rapid-brightly-firmly-0007")
    app = create_app()

    with TestClient(app) as client:
        owner_registration = client.post("/identities/register", json={"handle": owner.handle, "did": owner.did})
        assert owner_registration.status_code == 200
        stranger_registration = client.post(
            "/identities/register",
            json={"handle": stranger.handle, "did": stranger.did},
        )
        assert stranger_registration.status_code == 200
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
            f"/auth/sessions/{session.session_id}/resume",
            json={"data": {}},
            headers=_auth_header(
                tmp_path,
                "POST",
                f"/auth/sessions/{session.session_id}/resume",
                handle=stranger.handle,
            ),
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Proof JWT body hash does not match request"


def test_sessions_do_not_survive_app_recreation(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.delenv("AUTHSOME_DEPLOYMENT_MODE", raising=False)
    owner = create_identity(tmp_path, "steady-wisely-boldly-0042")
    session_id = ""

    with TestClient(create_app()) as first_client:
        registration = first_client.post("/identities/register", json={"handle": owner.handle, "did": owner.did})
        assert registration.status_code == 200
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

    with TestClient(create_app()) as second_client:
        response = second_client.get(
            f"/auth/sessions/{session_id}",
            headers=_auth_header(tmp_path, "GET", f"/auth/sessions/{session_id}", handle=owner.handle),
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Authentication session not found"
