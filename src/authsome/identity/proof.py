"""DID proof-of-possession JWT helpers."""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from authsome.identity.keys import public_key_from_did_key

POP_AUTH_SCHEME = "PoP"
DEFAULT_AUDIENCE = "authsome-daemon"
DEFAULT_TTL_SECONDS = 60


class ProofValidationError(ValueError):
    """Raised when a PoP JWT is missing, malformed, or not request-bound."""


@dataclass(frozen=True)
class ProofClaims:
    issuer: str
    subject: str
    expires_at: int
    jwt_id: str


class ReplayCache:
    """Small in-memory jti replay cache."""

    def __init__(self) -> None:
        self._seen: dict[str, int] = {}

    def check_and_store(self, jti: str, exp: int) -> None:
        now = int(time.time())
        self._seen = {key: value for key, value in self._seen.items() if value > now}
        if jti in self._seen:
            raise ProofValidationError("Proof JWT was already used")
        self._seen[jti] = exp


def body_sha256(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def create_proof_jwt(
    *,
    private_key: Ed25519PrivateKey,
    issuer: str,
    subject: str,
    method: str,
    path_query: str,
    body: bytes,
    audience: str = DEFAULT_AUDIENCE,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> str:
    now = int(time.time())
    payload = {
        "iss": issuer,
        "sub": subject,
        "aud": audience,
        "iat": now,
        "exp": now + ttl_seconds,
        "jti": str(uuid.uuid4()),
        "htm": method.upper(),
        "htu": path_query,
        "body_sha256": body_sha256(body),
    }
    return jwt.encode(payload, private_key, algorithm="EdDSA")


def validate_proof_jwt(
    *,
    token: str,
    method: str,
    path_query: str,
    body: bytes,
    replay_cache: ReplayCache | None = None,
    audience: str = DEFAULT_AUDIENCE,
) -> ProofClaims:
    unverified = _unverified_claims(token)
    issuer = _required_str(unverified, "iss")
    public_key = public_key_from_did_key(issuer)
    try:
        claims = jwt.decode(token, public_key, algorithms=["EdDSA"], audience=audience)
    except jwt.PyJWTError as exc:
        raise ProofValidationError(f"Invalid proof JWT: {exc}") from exc

    if _required_str(claims, "htm").upper() != method.upper():
        raise ProofValidationError("Proof JWT method does not match request")
    if _required_str(claims, "htu") != path_query:
        raise ProofValidationError("Proof JWT URL does not match request")
    if _required_str(claims, "body_sha256") != body_sha256(body):
        raise ProofValidationError("Proof JWT body hash does not match request")

    subject = _required_str(claims, "sub")
    jwt_id = _required_str(claims, "jti")
    exp = claims.get("exp")
    if not isinstance(exp, int):
        raise ProofValidationError("Proof JWT exp must be an integer")
    if replay_cache is not None:
        replay_cache.check_and_store(jwt_id, exp)
    return ProofClaims(issuer=issuer, subject=subject, expires_at=exp, jwt_id=jwt_id)


def _unverified_claims(token: str) -> dict[str, Any]:
    try:
        claims = jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError as exc:
        raise ProofValidationError(f"Malformed proof JWT: {exc}") from exc
    if not isinstance(claims, dict):
        raise ProofValidationError("Proof JWT claims must be an object")
    return claims


def _required_str(claims: dict[str, Any], name: str) -> str:
    value = claims.get(name)
    if not isinstance(value, str) or not value:
        raise ProofValidationError(f"Proof JWT missing string claim: {name}")
    return value
