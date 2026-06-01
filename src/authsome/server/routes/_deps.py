"""FastAPI dependency helpers."""

from __future__ import annotations

from datetime import timedelta

from fastapi import Depends, HTTPException, Request

from authsome.auth.sessions import AuthSession, AuthSessionStore
from authsome.identity.principal import PrincipalRole
from authsome.identity.proof import POP_AUTH_SCHEME, ProofValidationError, validate_proof_jwt
from authsome.server.credential_repository import CredentialRepository
from authsome.server.credential_service import CredentialService
from authsome.server.ownership import ResolvedOwnership
from authsome.server.store.repositories import VaultRegistry
from authsome.server.ui_sessions import UiSessionStore
from authsome.utils import utc_now

UI_SESSION_COOKIE_NAME = "authsome_ui_session"


def update_device_code_expiry(session: AuthSession) -> None:
    """Set the session expiry from the device-code ``expires_in`` hint, if present."""
    if "expires_in" not in session.payload:
        return
    try:
        session.expires_at = utc_now() + timedelta(seconds=int(session.payload["expires_in"]))
    except ValueError:
        pass


def build_auth_service(
    request: Request,
    *,
    identity: str | None,
    principal_id: str | None,
    principal_role: PrincipalRole = PrincipalRole.USER,
    vault_id: str,
) -> CredentialService:
    """Construct a CredentialService with explicit, pre-resolved context.

    Use this when vault_id is explicitly chosen (e.g. multi-vault UI traversal).
    For standard request auth, prefer ``_build_service`` which accepts a
    ``ResolvedOwnership`` produced by the ownership resolver.
    """
    credentials = CredentialRepository(
        request.app.state.vault,
        identity=identity,
        principal_id=principal_id,
        vault_id=vault_id,
    )
    return CredentialService(
        credentials=credentials,
        providers=request.app.state.provider_repository,
        identity=identity,
        principal_id=principal_id,
        principal_role=principal_role,
        vault_id=vault_id,
    )


def _build_service(request: Request, ownership: ResolvedOwnership) -> CredentialService:
    """Construct a CredentialService from a fully resolved ownership context."""
    return build_auth_service(
        request,
        identity=ownership.identity,
        principal_id=ownership.principal_id,
        principal_role=ownership.role,
        vault_id=ownership.vault_id,
    )


async def _resolve_identity_ownership(request: Request, identity: str) -> ResolvedOwnership:
    """Resolve and cache ownership for an identity handle."""
    resolved = request.app.state.ownership_cache.get(identity)
    if resolved is None:
        resolved = await request.app.state.ownership_resolver.resolve(identity=identity)
        request.app.state.ownership_cache[identity] = resolved
    return resolved


async def get_auth_service(
    request: Request,
    *,
    identity: str | None = None,
    principal_id: str | None = None,
) -> CredentialService | None:
    if identity is not None:
        resolved = await _resolve_identity_ownership(request, identity)
        return _build_service(request, resolved)

    if principal_id is None:
        return None

    resolved = await request.app.state.ownership_resolver.resolve_for_principal(principal_id=principal_id)
    if resolved is None:
        return None
    return _build_service(request, resolved)


async def require_auth_service(
    request: Request,
    *,
    identity: str | None = None,
    principal_id: str | None = None,
    status_code: int = 404,
    detail: str = "Authentication context not found",
) -> CredentialService:
    auth = await get_auth_service(request, identity=identity, principal_id=principal_id)
    if auth is None:
        raise HTTPException(status_code=status_code, detail=detail)
    return auth


async def verify_pop_caller(request: Request) -> ResolvedOwnership:
    """Validate the PoP JWT and return the caller's resolved ownership context.

    Layer 1 (caller identification): parse and validate the PoP JWT, confirm the
    identity handle is registered, and resolve its principal + vault via the
    ownership resolver. Populates ``request.state`` for downstream handlers.
    """
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

    registration = await request.app.state.store.identity_registry.resolve(claims.subject)
    if registration is None:
        raise HTTPException(status_code=401, detail="Unknown identity handle")
    if registration.did != claims.issuer:
        raise HTTPException(status_code=401, detail="Identity issuer does not match registered DID")

    try:
        resolved = await _resolve_identity_ownership(request, claims.subject)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    request.state.identity = claims.subject
    request.state.did = claims.issuer
    request.state.principal_id = resolved.principal_id
    request.state.vault_id = resolved.vault_id
    request.state.principal_role = resolved.role
    request.state.registration_status = "registered"
    return resolved


async def get_protected_auth_service(
    request: Request,
    ownership: ResolvedOwnership = Depends(verify_pop_caller),
) -> CredentialService:
    """Layer 2 (service construction): build CredentialService for a PoP-verified caller."""
    return _build_service(request, ownership)


async def get_admin_auth_service(
    auth: CredentialService = Depends(get_protected_auth_service),
) -> CredentialService:
    if auth.principal_role != PrincipalRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin role required")
    return auth


async def get_daemon_or_browser_auth_service(request: Request) -> CredentialService:
    """Resolve auth from PoP headers or an existing browser dashboard session."""
    if request.headers.get("Authorization"):
        ownership = await verify_pop_caller(request)
        return _build_service(request, ownership)

    await resolve_ui_request_identity(request)
    auth = await get_auth_service(
        request,
        principal_id=getattr(request.state, "ui_principal_id", None),
    )
    if auth is None:
        raise HTTPException(status_code=401, detail="Missing or invalid browser session")
    return auth


async def get_admin_daemon_or_browser_auth_service(request: Request) -> CredentialService:
    auth = await get_daemon_or_browser_auth_service(request)
    if auth.principal_role != PrincipalRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin role required")
    return auth


def get_vault_registry(request: Request) -> VaultRegistry:
    return request.app.state.store.vaults


def get_auth_sessions(request: Request) -> AuthSessionStore:
    return request.app.state.auth_sessions


def get_server_base_url(request: Request) -> str:
    return request.app.state.server_base_url


def get_ui_sessions(request: Request) -> UiSessionStore:
    return request.app.state.ui_sessions


async def resolve_ui_request_identity(request: Request) -> None:
    """Populate request.state with the principal bound to a browser UI session cookie."""
    cookie_value = request.cookies.get(UI_SESSION_COOKIE_NAME)
    if not cookie_value:
        return

    try:
        session = request.app.state.ui_sessions.get_browser_session(cookie_value)
    except KeyError:
        return

    request.state.ui_identity = None
    request.state.ui_principal_id = session.principal_id
    principal = await request.app.state.store.principals.get(session.principal_id)
    request.state.ui_principal_role = principal.role if principal else None
    request.state.ui_email = session.email
