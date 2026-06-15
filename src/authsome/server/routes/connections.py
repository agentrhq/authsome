"""Connection routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from authsome.auth.models.enums import ExportFormat
from authsome.identity.principal import PrincipalRole
from authsome.server.analytics import capture_event
from authsome.server.credential_service import CredentialService
from authsome.server.routes._deps import (
    build_auth_service,
    get_daemon_or_browser_auth_service,
    get_protected_auth_service,
    get_vault_registry,
    require_auth_service,
)
from authsome.server.schemas import ConnectionDetailResponse, ConnectionSecretsResponse
from authsome.server.store.repositories import VaultRegistry

router = APIRouter(tags=["connections"])


def _actor(auth: CredentialService) -> str:
    return auth.identity or auth.principal_id or "account-ui"


async def _connection_detail(
    auth: CredentialService,
    provider: str,
    connection: str,
    *,
    can_set_default: bool,
    can_set_global: bool,
) -> ConnectionDetailResponse:
    definition = await auth.get_provider(provider)
    record = await auth.get_connection(provider, connection)
    global_pointer = await auth.global_connections.get(provider)
    is_global = (
        global_pointer is not None
        and global_pointer.owner_principal_id == record.principal_id
        and global_pointer.owner_vault_id == record.vault_id
        and global_pointer.connection_name == record.connection_name
    )
    return ConnectionDetailResponse(
        provider=record.provider,
        provider_display_name=definition.display_name,
        connection_name=record.connection_name,
        principal_id=record.principal_id,
        identity=record.identity,
        vault_id=record.vault_id,
        status=record.status.value,
        auth_type=record.auth_type.value,
        base_url=record.base_url,
        api_url=record.api_url,
        scopes=list(record.scopes or []),
        token_type=record.token_type,
        obtained_at=record.obtained_at,
        expires_at=record.expires_at,
        account=record.account.model_dump(mode="json") if record.account else None,
        secrets=ConnectionSecretsResponse(
            access_token=record.access_token,
            refresh_token=record.refresh_token,
            api_key=record.api_key,
            credentials=dict(record.credentials or {}),
        ),
        can_set_default=can_set_default,
        can_set_global=can_set_global,
        is_global=is_global,
    )


async def _provider_connection_counts(request: Request, auth: CredentialService) -> dict[str, int]:
    if auth.principal_role != PrincipalRole.ADMIN:
        return {}

    counts: dict[str, int] = {}
    for principal in await request.app.state.store.principals.list_all():
        resolved = await request.app.state.ownership_resolver.resolve_for_principal(principal_id=principal.principal_id)
        if resolved is None:
            continue
        principal_auth = build_auth_service(
            request,
            identity=None,
            principal_id=principal.principal_id,
            principal_role=principal.role,
            vault_id=resolved.vault_id,
        )
        for group in await principal_auth.list_connections():
            counts[group["name"]] = counts.get(group["name"], 0) + len(group["connections"])
    return counts


@router.get("/connections")
async def list_connections(
    request: Request,
    auth: CredentialService = Depends(get_daemon_or_browser_auth_service),
):
    by_source = await auth.list_providers_by_source()
    return {
        "connections": await auth.list_connections(),
        "global_connections": [row.model_dump(mode="json") for row in await auth.list_global_connection_summaries()],
        "provider_connection_counts": await _provider_connection_counts(request, auth),
        "by_source": {
            source: [provider.model_dump(mode="json") for provider in providers]
            for source, providers in by_source.items()
        },
    }


@router.get("/connections/{provider}/{connection}")
async def get_connection(provider: str, connection: str, auth: CredentialService = Depends(get_protected_auth_service)):
    return (await auth.get_connection(provider, connection)).model_dump(mode="json")


@router.get("/connections/{provider}/{connection}/detail", response_model=ConnectionDetailResponse)
async def get_connection_detail(
    provider: str,
    connection: str,
    request: Request,
    principal: str | None = None,
    auth: CredentialService = Depends(get_daemon_or_browser_auth_service),
):
    target = await require_auth_service(
        request,
        principal_id=principal or auth.principal_id,
        acting_auth=auth,
        require_admin_for_other_principal=True,
        detail="Principal not found",
    )
    return await _connection_detail(
        target,
        provider,
        connection,
        can_set_default=target.principal_id == auth.principal_id,
        can_set_global=auth.principal_role == PrincipalRole.ADMIN and target.principal_id == auth.principal_id,
    )


@router.post("/connections/{provider}/{connection}/logout")
async def logout(
    provider: str,
    connection: str,
    request: Request,
    principal: str | None = None,
    auth: CredentialService = Depends(get_daemon_or_browser_auth_service),
):
    target = await require_auth_service(
        request,
        principal_id=principal or auth.principal_id,
        acting_auth=auth,
        require_admin_for_other_principal=True,
        detail="Principal not found",
    )
    await target.logout(provider, connection)
    capture_event(
        _actor(auth),
        "connection logout",
        {
            "provider": provider,
            "connection": connection,
            "principal_id": target.principal_id,
            "requested_by_principal_id": auth.principal_id,
        },
    )
    return {"status": "ok"}


@router.post("/connections/{provider}/revoke")
async def revoke(
    provider: str,
    auth: CredentialService = Depends(get_daemon_or_browser_auth_service),
    vault_registry: VaultRegistry = Depends(get_vault_registry),
):
    if auth.principal_role != PrincipalRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    all_vaults = await vault_registry.list_all()
    vault_ids: list[str] = [v.vault_id for v in all_vaults] or ([auth.vault_id] if auth.vault_id else [])
    await auth.revoke(provider, vault_ids=vault_ids)
    capture_event(
        _actor(auth),
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
    auth: CredentialService = Depends(get_daemon_or_browser_auth_service),
):
    await auth.set_default_connection(provider, connection)
    return {"status": "ok", "provider": provider, "default_connection": connection}


@router.post("/connections/{provider}/{connection}/global")
async def set_global_connection(
    provider: str,
    connection: str,
    auth: CredentialService = Depends(get_daemon_or_browser_auth_service),
):
    if auth.principal_role != PrincipalRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    record = await auth.set_global_connection(provider, connection)
    capture_event(
        _actor(auth),
        "connection made global",
        {
            "provider": provider,
            "connection": connection,
            "principal_id": auth.principal_id,
        },
    )
    return {
        "status": "ok",
        "provider": record.provider,
        "connection_name": record.connection_name,
    }


@router.delete("/connections/{provider}/global")
async def unset_global_connection(
    provider: str,
    auth: CredentialService = Depends(get_daemon_or_browser_auth_service),
):
    if auth.principal_role != PrincipalRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    deleted = await auth.unset_global_connection(provider)
    capture_event(
        _actor(auth),
        "global connection removed",
        {
            "provider": provider,
            "principal_id": auth.principal_id,
            "deleted": deleted,
        },
    )
    return {"status": "ok", "provider": provider, "deleted": deleted}


@router.post("/credentials/export")
async def export_credentials(body: dict, auth: CredentialService = Depends(get_protected_auth_service)):
    provider = body.get("provider")
    connection = body.get("connection", "default")
    export_format = ExportFormat(body.get("format", "env"))
    result = await auth.export(provider, connection, format=export_format)
    capture_event(
        auth.require_identity(),
        "credentials exported",
        {
            "provider": provider,
            "format": export_format.value,
            "principal_id": auth.principal_id,
        },
    )
    return {"output": result}
