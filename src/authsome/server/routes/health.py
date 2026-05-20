"""Health and readiness routes."""

from __future__ import annotations

from typing import Literal, cast

from fastapi import APIRouter, Depends, Request

from authsome import __version__
from authsome.auth import AuthService
from authsome.server.dependencies import get_deployment_mode
from authsome.server.routes._deps import get_auth_service, get_protected_auth_service, get_server_base_url
from authsome.server.schemas import HealthResponse, ReadyResponse

router = APIRouter()


def _describe_vault_encryption(auth: AuthService) -> tuple[str | None, str | None]:
    """Best-effort effective encryption details for health-style responses."""
    try:
        return auth.vault.crypto_source, auth.vault.crypto_source_description
    except Exception as exc:
        return None, f"Unavailable ({exc})"


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    mode = get_deployment_mode()
    response_mode = cast(Literal["local", "hosted"], mode if mode == "hosted" else "local")
    return HealthResponse(
        status="ok",
        version=__version__,
        mode=response_mode,
        configured_encryption_mode=request.app.state.server_config.encryption.mode,
    )


@router.get("/ready", response_model=ReadyResponse)
async def ready(auth: AuthService = Depends(get_auth_service)) -> ReadyResponse:
    checks: dict[str, str] = {}
    issues: list[str] = []
    warnings: list[str] = []
    configured_mode = auth.vault.crypto_mode

    checks["spec_version"] = "ok"

    # 1. Active Identity Check
    try:
        await auth.get_identity(auth.identity)
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
        conn_list = await auth.list_connections()
        checks["connections"] = "ok"
        connected_count = sum(1 for p in conn_list for c in p.get("connections", []) if c.get("status") == "connected")
        if connected_count == 0:
            warnings.append("no active provider connections found")
    except Exception as exc:
        checks["connections"] = "failed"
        issues.append(f"connections: {exc}")

    # 4. Vault Roundtrip & Store Integrity Check
    try:
        await auth.vault.put("__ready_test__", "ok", collection=f"vault:{auth.identity}")
        value = await auth.vault.get("__ready_test__", collection=f"vault:{auth.identity}")
        await auth.vault.delete("__ready_test__", collection=f"vault:{auth.identity}")
        checks["vault"] = "ok" if value == "ok" else "failed"
        if value != "ok":
            issues.append("vault: readiness roundtrip failed")
            checks["vault"] = "failed"
        else:
            checks["vault"] = "ok"

        if not await auth.vault.check_integrity(identity=auth.identity):
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
    effective_source, backend_description = _describe_vault_encryption(auth)
    return ReadyResponse(
        status=status,
        checks=checks,
        issues=issues,
        warnings=warnings,
        configured_encryption_mode=configured_mode,
        effective_encryption_source=effective_source,
        encryption_backend=backend_description,
    )


@router.get("/whoami")
async def whoami(
    request: Request,
    auth: AuthService = Depends(get_protected_auth_service),
    server_base_url: str = Depends(get_server_base_url),
) -> dict[str, str]:
    effective_source, backend_description = _describe_vault_encryption(auth)
    return {
        "version": __version__,
        "home": str(auth.vault.home),
        "identity": auth.identity,
        "active_identity": auth.identity,
        "did": getattr(request.state, "did", ""),
        "registration_status": getattr(request.state, "registration_status", "registered"),
        "daemon_url": server_base_url,
        "configured_encryption_mode": request.app.state.server_config.encryption.mode,
        "effective_encryption_source": effective_source or "unavailable",
        "encryption_backend": backend_description or "Unavailable",
    }
