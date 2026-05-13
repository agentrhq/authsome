"""Proxy support routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from authsome.auth import AuthService
from authsome.server.routes._deps import get_protected_auth_service
from authsome.server.schemas import (
    CredentialResolutionRequest,
    CredentialResolutionResponse,
    ProxyRoutesResponse,
)

router = APIRouter(tags=["proxy"])


@router.get("/proxy/routes", response_model=ProxyRoutesResponse)
async def proxy_routes(auth: AuthService = Depends(get_protected_auth_service)) -> ProxyRoutesResponse:
    data = await auth.proxy_routes()
    return ProxyRoutesResponse.model_validate(data)


@router.post("/credentials/resolve", response_model=CredentialResolutionResponse)
async def resolve_credentials(
    body: CredentialResolutionRequest,
    auth: AuthService = Depends(get_protected_auth_service),
) -> CredentialResolutionResponse:
    data = await auth.resolve_credentials(provider=body.provider, connection=body.connection)
    return CredentialResolutionResponse.model_validate(data)
