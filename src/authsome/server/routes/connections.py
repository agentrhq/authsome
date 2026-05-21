"""Connection routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from authsome.auth.models.enums import ExportFormat
from authsome.server.analytics import capture_event
from authsome.server.credential_service import AuthService
from authsome.server.registries import VaultRegistry
from authsome.server.routes._deps import get_protected_auth_service, get_vault_registry

router = APIRouter(tags=["connections"])


@router.get("/connections")
async def list_connections(auth: AuthService = Depends(get_protected_auth_service)):
    by_source = await auth.list_providers_by_source()
    return {
        "connections": await auth.list_connections(),
        "by_source": {
            source: [provider.model_dump(mode="json") for provider in providers]
            for source, providers in by_source.items()
        },
    }


@router.get("/connections/{provider}/{connection}")
async def get_connection(provider: str, connection: str, auth: AuthService = Depends(get_protected_auth_service)):
    return (await auth.get_connection(provider, connection)).model_dump(mode="json")


@router.post("/connections/{provider}/{connection}/logout")
async def logout(provider: str, connection: str, auth: AuthService = Depends(get_protected_auth_service)):
    await auth.logout(provider, connection)
    capture_event(
        auth.identity,
        "connection logout",
        {
            "provider": provider,
            "connection": connection,
            "principal_id": auth.principal_id,
        },
    )
    return {"status": "ok"}


@router.post("/connections/{provider}/revoke")
async def revoke(
    provider: str,
    auth: AuthService = Depends(get_protected_auth_service),
    vault_registry: VaultRegistry = Depends(get_vault_registry),
):
    all_vaults = await vault_registry.list_all()
    vault_ids: list[str] = [v.vault_id for v in all_vaults] or ([auth.vault_id] if auth.vault_id else [])
    await auth.revoke(provider, vault_ids=vault_ids)
    capture_event(
        auth.identity,
        "connection revoked",
        {
            "provider": provider,
            "principal_id": auth.principal_id,
        },
    )
    return {"status": "ok"}


@router.post("/connections/{provider}/{connection}/default")
async def set_default_connection(
    provider: str,
    connection: str,
    auth: AuthService = Depends(get_protected_auth_service),
):
    await auth.set_default_connection(provider, connection)
    return {"status": "ok", "provider": provider, "default_connection": connection}


@router.post("/credentials/export")
async def export_credentials(body: dict, auth: AuthService = Depends(get_protected_auth_service)):
    provider = body.get("provider")
    connection = body.get("connection", "default")
    export_format = ExportFormat(body.get("format", "env"))
    result = await auth.export(provider, connection, format=export_format)
    capture_event(
        auth.identity,
        "credentials exported",
        {
            "provider": provider,
            "format": export_format.value,
            "principal_id": auth.principal_id,
        },
    )
    return {"output": result}
