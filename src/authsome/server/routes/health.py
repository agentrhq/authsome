"""Health and readiness routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from authsome import __version__
from authsome.auth import AuthService
from authsome.auth.models.config import current_spec_version
from authsome.server.routes._deps import get_auth_service, get_protected_auth_service, get_server_base_url
from authsome.server.schemas import HealthResponse, ReadyResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", version=__version__)


@router.get("/ready", response_model=ReadyResponse)
async def ready(auth: AuthService = Depends(get_auth_service)) -> ReadyResponse:
    checks: dict[str, str] = {}
    issues: list[str] = []
    warnings: list[str] = []

    # 1. Config & Schema Version Check
    try:
        config = await auth.vault.get_config()
        checks["config"] = "ok"

        expected_spec_version = current_spec_version()
        if getattr(config, "spec_version", None) != expected_spec_version:
            issues.append(
                f"config: spec_version mismatch (got {config.spec_version}, expected {expected_spec_version})"
            )
            checks["version_compatibility"] = "failed"
        else:
            checks["version_compatibility"] = "ok"
    except Exception as exc:
        checks["config"] = "failed"
        checks["version_compatibility"] = "failed"
        issues.append(f"config: {exc}")

    # 2. Active Identity Check
    try:
        await auth.get_identity(auth.identity)
        checks["identity"] = "ok"
    except Exception as exc:
        checks["identity"] = "failed"
        issues.append(f"identity: {exc}")

    # 3. Providers List Check
    try:
        await auth.list_providers()
        checks["providers"] = "ok"
    except Exception as exc:
        checks["providers"] = "failed"
        issues.append(f"providers: {exc}")

    # 4. Connected Providers Check
    try:
        conn_list = await auth.list_connections()
        checks["connections"] = "ok"
        connected_count = sum(1 for p in conn_list for c in p.get("connections", []) if c.get("status") == "connected")
        if connected_count == 0:
            warnings.append("no active provider connections found")
    except Exception as exc:
        checks["connections"] = "failed"
        issues.append(f"connections: {exc}")

    # 5. Vault Roundtrip & Store Integrity Check
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
    return ReadyResponse(status=status, checks=checks, issues=issues, warnings=warnings)


@router.get("/whoami")
async def whoami(
    request: Request,
    auth: AuthService = Depends(get_protected_auth_service),
    server_base_url: str = Depends(get_server_base_url),
) -> dict[str, str]:
    config = await auth.vault.get_config()
    enc_mode = config.encryption.mode if config.encryption else "local_key"
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
        "did": getattr(request.state, "did", ""),
        "registration_status": getattr(request.state, "registration_status", "registered"),
        "daemon_url": server_base_url,
        "encryption_backend": enc_desc,
    }
