from pathlib import Path

import pytest

from authsome.identity import create_identity, load_private_key
from authsome.identity.proof import ReplayCache, create_proof_jwt, validate_proof_jwt


def _token(tmp_path: Path, *, method: str = "POST", path: str = "/connections", body: bytes = b"{}") -> str:
    identity = create_identity(tmp_path, "steady-wisely-boldly-0042")
    private_key = load_private_key(tmp_path, identity.handle)
    return create_proof_jwt(
        private_key=private_key,
        issuer=identity.did,
        subject=identity.handle,
        method=method,
        path_query=path,
        body=body,
    )


def test_validate_proof_jwt_accepts_valid_token(tmp_path: Path) -> None:
    token = _token(tmp_path)

    claims = validate_proof_jwt(token=token, method="POST", path_query="/connections", body=b"{}")

    assert claims.subject == "steady-wisely-boldly-0042"
    assert claims.issuer.startswith("did:key:z6Mk")


def test_validate_proof_jwt_rejects_wrong_method(tmp_path: Path) -> None:
    token = _token(tmp_path)

    with pytest.raises(ValueError, match="method"):
        validate_proof_jwt(token=token, method="GET", path_query="/connections", body=b"{}")


def test_validate_proof_jwt_rejects_wrong_body(tmp_path: Path) -> None:
    token = _token(tmp_path)

    with pytest.raises(ValueError, match="body hash"):
        validate_proof_jwt(token=token, method="POST", path_query="/connections", body=b'{"x":1}')


def test_validate_proof_jwt_rejects_replay(tmp_path: Path) -> None:
    token = _token(tmp_path)
    cache = ReplayCache()

    validate_proof_jwt(token=token, method="POST", path_query="/connections", body=b"{}", replay_cache=cache)
    with pytest.raises(ValueError, match="already used"):
        validate_proof_jwt(token=token, method="POST", path_query="/connections", body=b"{}", replay_cache=cache)
