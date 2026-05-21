"""Connection routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from authsome.auth import AuthService
from authsome.auth.models.enums import ExportFormat
from authsome.server.analytics import get_posthog
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
    ph = get_posthog()
    if ph is not None:
        ph.capture(
            "connection logout",
            distinct_id=auth.identity,
            properties={"provider": provider, "connection": connection, "principal_id": auth.principal_id},
        )
    return {"status": "ok"}


@router.post("/connections/{provider}/revoke")
async def revoke(provider: str, auth: AuthService = Depends(get_protected_auth_service)):
    await auth.revoke(provider)
    ph = get_posthog()
    if ph is not None:
        ph.capture(
            "connection revoked",
            distinct_id=auth.identity,
            properties={"provider": provider, "principal_id": auth.principal_id},
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
    ph = get_posthog()
    if ph is not None:
        ph.capture(
            "credentials exported",
            distinct_id=auth.identity,
            properties={
                "provider": provider,
                "format": export_format.value,
                "principal_id": auth.principal_id,
            },
        )
    return {"output": result}
