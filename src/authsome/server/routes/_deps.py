"""FastAPI dependency helpers."""

from __future__ import annotations

from fastapi import HTTPException, Request

from authsome.auth import AuthService
from authsome.auth.sessions import AuthSessionStore
from authsome.identity.proof import POP_AUTH_SCHEME, ProofValidationError, validate_proof_jwt


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


def get_auth_service_for_identity(request: Request, identity: str) -> AuthService:
    return AuthService(vault=request.app.state.vault, identity=identity)


async def get_protected_auth_service(request: Request) -> AuthService:
    authorization = request.headers.get("Authorization")
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing PoP authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme != POP_AUTH_SCHEME or not token:
        raise HTTPException(status_code=401, detail="Expected Authorization: PoP <jwt>")

    body = await request.body()
    # htu is path-only (not full URI) by design — the daemon is local-only,
    # so origin binding adds no security benefit and complicates proxy setups.
    path_query = request.url.path
    if request.url.query:
        path_query = f"{path_query}?{request.url.query}"
    try:
        claims = validate_proof_jwt(
            token=token,
            method=request.method,
            path_query=path_query,
            body=body,
            replay_cache=request.app.state.proof_replay_cache,
        )
    except (ProofValidationError, ValueError) as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    registration = request.app.state.identity_registry.resolve(claims.subject)
    if registration is None:
        raise HTTPException(status_code=401, detail="Unknown identity handle")
    if registration.did != claims.issuer:
        raise HTTPException(status_code=401, detail="Identity issuer does not match registered DID")

    request.state.identity = claims.subject
    request.state.did = claims.issuer
    request.state.registration_status = "registered"
    return get_auth_service_for_identity(request, claims.subject)


def get_auth_sessions(request: Request) -> AuthSessionStore:
    return request.app.state.auth_sessions


def get_server_base_url(request: Request) -> str:
    return request.app.state.server_base_url
