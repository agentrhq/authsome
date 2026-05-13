"""Connection routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from authsome.auth import AuthService
from authsome.auth.models.enums import ExportFormat
from authsome.server.routes._deps import get_protected_auth_service

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
    return {"status": "ok"}


@router.post("/connections/{provider}/revoke")
async def revoke(provider: str, auth: AuthService = Depends(get_protected_auth_service)):
    await auth.revoke(provider)
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
    return {"output": await auth.export(provider, connection, format=export_format)}
