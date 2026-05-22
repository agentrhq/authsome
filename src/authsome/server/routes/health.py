"""Health and readiness routes."""

from __future__ import annotations

import asyncio
import secrets
from typing import Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Request

from authsome import __version__
from authsome.server.credential_service import AuthService
from authsome.server.dependencies import get_deployment_mode
from authsome.server.routes._deps import get_protected_auth_service, get_server_base_url
from authsome.server.schemas import HealthResponse, ReadyResponse
from authsome.utils import connection_is_active

router = APIRouter()


def _describe_vault_encryption(vault) -> tuple[str | None, str | None]:
    """Return effective vault encryption details for API output."""
    try:
        return vault.crypto_source, vault.crypto_source_description
    except Exception as exc:
        return None, f"Unavailable ({exc})"


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    mode = get_deployment_mode()
    response_mode = cast(Literal["local", "hosted"], mode if mode == "hosted" else "local")
    effective_source, backend_description = _describe_vault_encryption(request.app.state.vault)
    return HealthResponse(
        status="ok",
        version=__version__,
        mode=response_mode,
        configured_encryption_mode=request.app.state.server_config.encryption.mode,
        effective_encryption_source=effective_source,
        encryption_backend=backend_description,
    )


@router.get("/ready", response_model=ReadyResponse)
async def ready(
    request: Request,
    auth: AuthService = Depends(get_protected_auth_service),
) -> ReadyResponse:
    checks: dict[str, str] = {}
    issues: list[str] = []
    warnings: list[str] = []

    checks["spec_version"] = "ok"

    vault = request.app.state.vault
    configured_mode = vault.crypto_mode

    # 1. Active Identity Check — scoped to the authenticated caller
    checks["identity"] = "ok"

    # 2. Providers List Check
    try:
        await auth.list_providers()
        checks["providers"] = "ok"
    except Exception as exc:
        checks["providers"] = "failed"
        issues.append(f"providers: {exc}")

    # 3. Connected Providers Check
    try:
        conn_list = await auth.list_connections()
        checks["connections"] = "ok"
        connected_count = sum(1 for p in conn_list for c in p.get("connections", []) if connection_is_active(c))
        if connected_count == 0:
            warnings.append("no active provider connections found")
    except Exception as exc:
        checks["connections"] = "failed"
        issues.append(f"connections: {exc}")

    # 4. Vault Roundtrip & Store Integrity Check
    try:
        await vault.put("__ready_test__", "ok", collection="vault:__ready__")
        value = await vault.get("__ready_test__", collection="vault:__ready__")
        await vault.delete("__ready_test__", collection="vault:__ready__")
        if value != "ok":
            issues.append("vault: readiness roundtrip failed")
            checks["vault"] = "failed"
        else:
            checks["vault"] = "ok"

        if not await vault.check_integrity(identity="__ready__"):
            issues.append("vault: store failed integrity check")
            checks["integrity"] = "failed"
        else:
            checks["integrity"] = "ok"
    except Exception as exc:
        checks["vault"] = "failed"
        checks["integrity"] = "failed"
        issues.append(f"vault: {exc}")

    status = "ready" if not issues else "not_ready"
    effective_source, backend_description = _describe_vault_encryption(vault)
    return ReadyResponse(
        status=status,
        checks=checks,
        issues=issues,
        warnings=warnings,
        configured_encryption_mode=configured_mode,
        effective_encryption_source=effective_source,
        encryption_backend=backend_description,
    )


_rekey_lock = asyncio.Lock()


@router.post("/rekey")
async def rekey(
    request: Request,
    auth: AuthService = Depends(get_protected_auth_service),
) -> dict[str, str]:
    _ = request
    async with _rekey_lock:
        new_key_bytes = secrets.token_bytes(32)
        try:
            await auth.vault.rekey(new_key_bytes)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"status": "ok", "message": "Master key successfully rotated"}


@router.get("/whoami")
async def whoami(
    request: Request,
    auth: AuthService = Depends(get_protected_auth_service),
    server_base_url: str = Depends(get_server_base_url),
) -> dict[str, str]:
    effective_source, backend_description = _describe_vault_encryption(auth.vault)
    identity = auth.require_identity()
    return {
        "version": __version__,
        "home": str(request.app.state.store.home),
        "identity": identity,
        "active_identity": identity,
        "principal_id": getattr(request.state, "principal_id", ""),
        "vault_id": getattr(request.state, "vault_id", ""),
        "did": getattr(request.state, "did", ""),
        "registration_status": getattr(request.state, "registration_status", "registered"),
        "daemon_url": server_base_url,
        "configured_encryption_mode": request.app.state.server_config.encryption.mode,
        "effective_encryption_source": effective_source or "unavailable",
        "encryption_backend": backend_description or "Unavailable",
    }
