from pathlib import Path

from fastapi.testclient import TestClient

from authsome.identity.keys import create_identity, load_private_key
from authsome.identity.proof import create_proof_jwt
from authsome.server.app import create_app


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
    assert response.json()["did"].startswith("did:key:z6Mk")


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
