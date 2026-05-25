"""FastAPI dependency helpers."""

from __future__ import annotations

from fastapi import HTTPException, Request

from authsome.auth.sessions import AuthSessionStore
from authsome.identity import current_from_home
from authsome.identity.proof import POP_AUTH_SCHEME, ProofValidationError, validate_proof_jwt
from authsome.server.credential_service import AuthService
from authsome.server.dependencies import get_deployment_mode
from authsome.server.registries import VaultRegistry
from authsome.server.ui_sessions import UiSessionStore

UI_SESSION_COOKIE_NAME = "authsome_ui_session"


async def get_auth_service(
    request: Request,
    *,
    identity: str | None = None,
    principal_id: str | None = None,
) -> AuthService | None:
    if identity is not None:
        resolved = request.app.state.ownership_cache.get(identity)
        if resolved is None:
            resolved = await request.app.state.ownership_resolver.resolve(identity=identity)
            request.app.state.ownership_cache[identity] = resolved
        return AuthService(
            vault=request.app.state.vault,
            identity=identity,
            principal_id=resolved.principal_id,
            vault_id=resolved.vault_id,
            deployment_mode=get_deployment_mode(),
        )

    if principal_id is None:
        return None

    binding = await request.app.state.principal_vault_binding_registry.get_default_vault(principal_id)
    if binding is None:
        return None
    return AuthService(
        vault=request.app.state.vault,
        identity=None,
        principal_id=principal_id,
        vault_id=binding.vault_id,
        deployment_mode=get_deployment_mode(),
    )


async def require_auth_service(
    request: Request,
    *,
    identity: str | None = None,
    principal_id: str | None = None,
    status_code: int = 404,
    detail: str = "Authentication context not found",
) -> AuthService:
    auth = await get_auth_service(request, identity=identity, principal_id=principal_id)
    if auth is None:
        raise HTTPException(status_code=status_code, detail=detail)
    return auth


async def get_principal_browser_auth_service(request: Request) -> AuthService:
    cookie_value = request.cookies.get(UI_SESSION_COOKIE_NAME)
    if not cookie_value:
        raise HTTPException(status_code=401, detail="Missing hosted browser session")

    try:
        session = request.app.state.ui_sessions.get_browser_session(cookie_value)
    except KeyError as exc:
        raise HTTPException(status_code=401, detail="Hosted browser session expired") from exc

    auth = await require_auth_service(
        request,
        principal_id=session.principal_id,
        status_code=403,
        detail="Principal has no default vault",
    )
    request.state.ui_identity = None
    request.state.ui_principal_id = session.principal_id
    request.state.ui_email = session.email
    request.state.ui_session_token = session.token
    return auth


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

    registration = await request.app.state.identity_registry.resolve(claims.subject)
    if registration is None:
        raise HTTPException(status_code=401, detail="Unknown identity handle")
    if registration.did != claims.issuer:
        raise HTTPException(status_code=401, detail="Identity issuer does not match registered DID")

    try:
        resolved = await request.app.state.ownership_resolver.resolve(identity=claims.subject)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    request.state.identity = claims.subject
    request.state.did = claims.issuer
    request.state.principal_id = resolved.principal_id
    request.state.vault_id = resolved.vault_id
    request.state.registration_status = "registered"
    request.app.state.ownership_cache[claims.subject] = resolved
    return await require_auth_service(
        request,
        identity=claims.subject,
        status_code=500,
        detail="Ownership context not resolved",
    )


def get_vault_registry(request: Request) -> VaultRegistry:
    return request.app.state.vault_registry


def get_auth_sessions(request: Request) -> AuthSessionStore:
    return request.app.state.auth_sessions


def get_server_base_url(request: Request) -> str:
    return request.app.state.server_base_url


def get_ui_sessions(request: Request) -> UiSessionStore:
    return request.app.state.ui_sessions


async def resolve_ui_request_identity(request: Request) -> str | None:
    """Resolve the identity bound to a browser UI request."""
    if get_deployment_mode() != "hosted":
        identity = await current_from_home(request.app.state.store.home)
        request.state.ui_identity = identity.handle
        try:
            resolved = await request.app.state.ownership_resolver.resolve(identity=identity.handle)
            request.state.ui_principal_id = resolved.principal_id
        except ValueError:
            request.state.ui_principal_id = None
        return identity.handle

    cookie_value = request.cookies.get(UI_SESSION_COOKIE_NAME)
    if not cookie_value:
        return None

    try:
        session = request.app.state.ui_sessions.get_browser_session(cookie_value)
    except KeyError:
        return None

    request.state.ui_identity = None
    request.state.ui_principal_id = session.principal_id
    request.state.ui_email = session.email
    request.state.ui_session_token = session.token
    return None
