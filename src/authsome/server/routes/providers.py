"""Provider routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from authsome.auth import AuthService
from authsome.auth.models.provider import ProviderDefinition
from authsome.server.analytics import get_posthog
from authsome.server.routes._deps import get_protected_auth_service

router = APIRouter(prefix="/providers", tags=["providers"])


@router.get("")
async def list_providers(auth: AuthService = Depends(get_protected_auth_service)):
    by_source = await auth.list_providers_by_source()
    return {
        source: [provider.model_dump(mode="json") for provider in providers] for source, providers in by_source.items()
    }


@router.get("/{provider}")
async def get_provider(provider: str, auth: AuthService = Depends(get_protected_auth_service)):
    return (await auth.get_provider(provider)).model_dump(mode="json")


@router.post("")
async def register_provider(body: dict, auth: AuthService = Depends(get_protected_auth_service)):
    definition_payload = body.get("definition", body)
    definition = ProviderDefinition.model_validate(definition_payload)
    await auth.register_provider(definition, force=bool(body.get("force", False)))
    ph = get_posthog()
    if ph is not None:
        ph.capture(
            "provider registered",
            distinct_id=auth.identity,
            properties={
                "provider": definition.name,
                "auth_type": definition.auth_type.value if definition.auth_type else None,
                "principal_id": auth.principal_id,
            },
        )
    return {"status": "ok", "provider": definition.name}


@router.delete("/{provider}")
async def delete_provider(provider: str, auth: AuthService = Depends(get_protected_auth_service)):
    await auth.remove(provider)
    ph = get_posthog()
    if ph is not None:
        ph.capture(
            "provider deleted",
            distinct_id=auth.identity,
            properties={"provider": provider, "principal_id": auth.principal_id},
        )
    return {"status": "ok", "provider": provider}
