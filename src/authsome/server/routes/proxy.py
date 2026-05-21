"""Proxy support routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from authsome.auth import AuthService
from authsome.server.analytics import get_posthog
from authsome.server.routes._deps import get_protected_auth_service
from authsome.server.schemas import (
    CredentialResolutionRequest,
    CredentialResolutionResponse,
    ProxyRoutesResponse,
)

router = APIRouter(tags=["proxy"])


@router.get("/proxy/routes", response_model=ProxyRoutesResponse)
async def proxy_routes(
    scope: str = Query("connected", pattern="^(connected|configured)$"),
    auth: AuthService = Depends(get_protected_auth_service),
) -> ProxyRoutesResponse:
    data = await auth.proxy_routes(scope=scope)
    return ProxyRoutesResponse.model_validate(data)


@router.post("/credentials/resolve", response_model=CredentialResolutionResponse)
async def resolve_credentials(
    body: CredentialResolutionRequest,
    auth: AuthService = Depends(get_protected_auth_service),
) -> CredentialResolutionResponse:
    data = await auth.resolve_credentials(provider=body.provider, connection=body.connection)
    ph = get_posthog()
    if ph is not None:
        ph.capture(
            "credentials resolved",
            distinct_id=auth.identity,
            properties={
                "provider": body.provider,
                "connection": body.connection,
                "principal_id": auth.principal_id,
            },
        )
    return CredentialResolutionResponse.model_validate(data)
