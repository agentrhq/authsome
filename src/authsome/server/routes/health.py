"""Health and readiness routes."""

from __future__ import annotations

from typing import Literal, cast

from fastapi import APIRouter, Depends, Request

from authsome import __version__
from authsome.auth import AuthService
from authsome.identity import current_from_home
from authsome.server.dependencies import get_deployment_mode
from authsome.server.ownership import OwnershipResolver
from authsome.server.routes._deps import get_auth_service, get_protected_auth_service, get_server_base_url
from authsome.server.schemas import HealthResponse, ReadyResponse
from authsome.utils import connection_is_active

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    mode = get_deployment_mode()
    response_mode = cast(Literal["local", "hosted"], mode if mode == "hosted" else "local")
    return HealthResponse(status="ok", version=__version__, mode=response_mode)


@router.get("/ready", response_model=ReadyResponse)
async def ready(request: Request, auth: AuthService = Depends(get_auth_service)) -> ReadyResponse:
    checks: dict[str, str] = {}
    issues: list[str] = []
    warnings: list[str] = []
    active_auth: AuthService | None = None

    checks["spec_version"] = "ok"

    # 1. Active Identity and Ownership Check
    try:
        active_identity = await current_from_home(auth.vault.home)
        ownership_resolver: OwnershipResolver = request.app.state.ownership_resolver
        resolved = await ownership_resolver.resolve(identity=active_identity.handle)
        active_auth = AuthService(
            vault=auth.vault,
            identity=active_identity.handle,
            principal_id=resolved.principal_id,
            vault_id=resolved.vault_id,
            deployment_mode=get_deployment_mode(),
        )
        await active_auth.get_identity(active_identity.handle)
        checks["identity"] = "ok"
    except Exception as exc:
        checks["identity"] = "failed"
        issues.append(f"identity: {exc}")

    # 2. Providers List Check
    try:
        await auth.list_providers()
        checks["providers"] = "ok"
    except Exception as exc:
        checks["providers"] = "failed"
        issues.append(f"providers: {exc}")

    # 3. Connected Providers Check
    try:
        if active_auth is None:
            raise ValueError("Active identity ownership context is unavailable")
        conn_list = await active_auth.list_connections()
        checks["connections"] = "ok"
        connected_count = sum(1 for p in conn_list for c in p.get("connections", []) if connection_is_active(c))
        if connected_count == 0:
            warnings.append("no active provider connections found")
    except Exception as exc:
        checks["connections"] = "failed"
        issues.append(f"connections: {exc}")

    # 4. Vault Roundtrip & Store Integrity Check
    try:
        if active_auth is None:
            raise ValueError("Active identity ownership context is unavailable")
        collection = f"vault:{active_auth.vault_id}"
        await auth.vault.put("__ready_test__", "ok", collection=collection)
        value = await auth.vault.get("__ready_test__", collection=collection)
        await auth.vault.delete("__ready_test__", collection=collection)
        checks["vault"] = "ok" if value == "ok" else "failed"
        if value != "ok":
            issues.append("vault: readiness roundtrip failed")
            checks["vault"] = "failed"
        else:
            checks["vault"] = "ok"

        if not await auth.vault.check_integrity(identity=active_auth.identity):
            issues.append("vault: store failed integrity check")
            checks["integrity"] = "failed"
        else:
            checks["integrity"] = "ok"
    except Exception as exc:
        checks["vault"] = "failed"
        checks["integrity"] = "failed"
        issues.append(f"vault: {exc}")

    # TODO: Re-enable master.key permission checks once backend implementation stabilizes.
    # (Previous implementation alerted users if file was world-readable)

    status = "ready" if not issues else "not_ready"
    return ReadyResponse(status=status, checks=checks, issues=issues, warnings=warnings)


@router.get("/whoami")
async def whoami(
    request: Request,
    auth: AuthService = Depends(get_protected_auth_service),
    server_base_url: str = Depends(get_server_base_url),
) -> dict[str, str]:
    enc_mode = request.app.state.server_config.encryption.mode
    if enc_mode == "local_key":
        enc_desc = f"Local Key ({auth.vault.home / 'server' / 'master.key'})"
    elif enc_mode == "keyring":
        enc_desc = "OS Keyring"
    else:
        enc_desc = enc_mode
    return {
        "version": __version__,
        "home": str(auth.vault.home),
        "identity": auth.identity,
        "active_identity": auth.identity,
        "principal_id": getattr(request.state, "principal_id", ""),
        "vault_id": getattr(request.state, "vault_id", ""),
        "did": getattr(request.state, "did", ""),
        "registration_status": getattr(request.state, "registration_status", "registered"),
        "daemon_url": server_base_url,
        "encryption_backend": enc_desc,
    }
