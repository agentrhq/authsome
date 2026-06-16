"""Provider routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from authsome.auth.models.connection import ConnectionRecord, ProviderClientRecord
from authsome.auth.models.provider import ProviderDefinition
from authsome.identity.principal import PrincipalRole
from authsome.server.analytics import capture_event
from authsome.server.credential_service import CredentialService
from authsome.server.routes._deps import (
    build_auth_service,
    get_daemon_or_browser_auth_service,
    get_protected_auth_service,
    get_server_base_url,
)
from authsome.server.schemas import (
    ConnectionSummaryResponse,
    ProviderClientResponse,
    ProviderConfigurationUpdateRequest,
    ProviderConfigurationUpdateResponse,
    ProviderDetailResponse,
    ProviderPrincipalUsageResponse,
)
from authsome.server.urls import build_callback_url

router = APIRouter(prefix="/providers", tags=["providers"])


def _actor(auth: CredentialService) -> str:
    return auth.identity or auth.principal_id or "account-ui"


def _connection_summary(record: ConnectionRecord, *, provider_display_name: str) -> ConnectionSummaryResponse:
    account_label = record.account.label if record.account else None
    return ConnectionSummaryResponse(
        provider=record.provider,
        provider_display_name=provider_display_name,
        connection_name=record.connection_name,
        status=record.status.value,
        auth_type=record.auth_type.value,
        account_label=account_label,
        principal_id=record.principal_id,
    )


def _client_response(record: ProviderClientRecord | None) -> ProviderClientResponse | None:
    if record is None:
        return None
    return ProviderClientResponse(
        client_id=record.client_id,
        client_secret=record.client_secret,
        base_url=record.base_url,
        api_url=record.api_url,
        scopes=list(record.scopes or []),
    )


async def _current_connections(
    auth: CredentialService,
    provider: str,
    display_name: str,
) -> list[ConnectionSummaryResponse]:
    records = await auth.list_connection_records(provider)
    return sorted(
        [_connection_summary(record, provider_display_name=display_name) for record in records],
        key=lambda row: row.connection_name,
    )


async def _admin_usage(
    request: Request,
    provider: str,
    display_name: str,
    role: PrincipalRole,
) -> list[ProviderPrincipalUsageResponse]:
    if role != PrincipalRole.ADMIN:
        return []
    groups: list[ProviderPrincipalUsageResponse] = []
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
        connections = await _current_connections(principal_auth, provider, display_name)
        if connections:
            groups.append(
                ProviderPrincipalUsageResponse(
                    principal_id=principal.principal_id,
                    email=principal.email,
                    connections=connections,
                )
            )
    return groups


@router.get("")
async def list_providers(auth: CredentialService = Depends(get_protected_auth_service)):
    by_source = await auth.list_providers_by_source()
    return {
        source: [provider.model_dump(mode="json") for provider in providers] for source, providers in by_source.items()
    }


@router.get("/{provider}")
async def get_provider(provider: str, auth: CredentialService = Depends(get_protected_auth_service)):
    return (await auth.get_provider(provider)).model_dump(mode="json")


@router.get("/{provider}/detail", response_model=ProviderDetailResponse)
async def get_provider_detail(
    provider: str,
    request: Request,
    auth: CredentialService = Depends(get_daemon_or_browser_auth_service),
    server_base_url: str = Depends(get_server_base_url),
):
    definition = await auth.get_provider(provider)
    is_admin = auth.principal_role == PrincipalRole.ADMIN
    client = await auth.get_provider_client(provider) if is_admin else None
    fields = await auth.get_provider_configuration_inputs(provider) if is_admin else []
    connections = await _current_connections(auth, provider, definition.display_name)
    return ProviderDetailResponse(
        provider=definition.model_dump(mode="json"),
        account={
            "principal_id": auth.principal_id,
            "role": auth.principal_role.value,
            "is_admin": is_admin,
        },
        client=_client_response(client),
        configuration_fields=[field.model_dump(mode="json", exclude_none=True) for field in fields],
        configuration_warning="Changing these credentials will revoke existing connections for this provider."
        if client
        else None,
        show_callback_helper=is_admin,
        callback_url=build_callback_url(server_base_url) if is_admin else None,
        connections=connections,
        principal_usage=await _admin_usage(request, provider, definition.display_name, auth.principal_role),
    )


@router.put("/{provider}/configuration", response_model=ProviderConfigurationUpdateResponse)
async def update_provider_configuration(
    provider: str,
    body: ProviderConfigurationUpdateRequest,
    request: Request,
    auth: CredentialService = Depends(get_daemon_or_browser_auth_service),
):
    if auth.principal_role != PrincipalRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    payload = body.model_dump(exclude_none=True)
    if isinstance(body.scopes, list):
        payload["scopes"] = ",".join(body.scopes)
    all_vaults = await request.app.state.store.vaults.list_all()
    vault_ids = [vault.vault_id for vault in all_vaults] or ([auth.vault_id] if auth.vault_id else [])
    changed = await auth.update_provider_configuration(provider, payload, vault_ids=vault_ids)
    capture_event(
        _actor(auth),
        "provider configuration updated",
        {"provider": provider, "changed": changed, "principal_id": auth.principal_id},
    )
    return ProviderConfigurationUpdateResponse(changed=changed, provider=provider)


@router.post("")
async def register_provider(body: dict, auth: CredentialService = Depends(get_daemon_or_browser_auth_service)):
    if auth.principal_role != PrincipalRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    definition_payload = body.get("definition", body)
    definition = ProviderDefinition.model_validate(definition_payload)
    await auth.register_provider(definition, force=bool(body.get("force", False)))
    capture_event(
        _actor(auth),
        "provider registered",
        {
            "provider": definition.name,
            "auth_type": definition.auth_type.value if definition.auth_type else None,
            "principal_id": auth.principal_id,
        },
    )
    return {"status": "ok", "provider": definition.name}


@router.put("/{provider}")
async def update_provider(
    provider: str,
    body: dict,
    auth: CredentialService = Depends(get_daemon_or_browser_auth_service),
):
    if auth.principal_role != PrincipalRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    definition_payload = body.get("definition", body)
    definition = ProviderDefinition.model_validate(definition_payload)
    await auth.update_provider(provider, definition)
    capture_event(
        _actor(auth),
        "provider updated",
        {
            "provider": definition.name,
            "auth_type": definition.auth_type.value if definition.auth_type else None,
            "principal_id": auth.principal_id,
        },
    )
    return {"status": "ok", "provider": definition.name}


@router.delete("/{provider}")
async def delete_provider(
    provider: str,
    auth: CredentialService = Depends(get_daemon_or_browser_auth_service),
):
    if auth.principal_role != PrincipalRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    await auth.remove(provider)
    capture_event(
        _actor(auth),
        "provider deleted",
        {
            "provider": provider,
            "principal_id": auth.principal_id,
        },
    )
    return {"status": "ok", "provider": provider}
