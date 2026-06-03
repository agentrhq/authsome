"""Identity registration routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from authsome.server.analytics import capture_event
from authsome.server.credential_service import CredentialService
from authsome.server.routes._deps import get_daemon_or_browser_auth_service
from authsome.server.store.repositories import IdentityRegistrationError

router = APIRouter(prefix="/identities", tags=["identities"])


class RegisterIdentityRequest(BaseModel):
    handle: str
    did: str


@router.get("")
@router.get("/")
async def list_identities(
    request: Request,
    auth: CredentialService = Depends(get_daemon_or_browser_auth_service),
) -> dict[str, list[dict[str, str]]]:
    claims = await request.app.state.store.identity_claims.list_for_principal(auth.principal_id)
    return {
        "identities": [
            {
                "handle": claim.identity_handle,
                "status": claim.claim_status.value,
            }
            for claim in claims
        ]
    }


@router.post("/register")
async def register_identity(body: RegisterIdentityRequest, request: Request) -> dict[str, str]:
    try:
        status = await request.app.state.identity_bootstrap.register_identity(handle=body.handle, did=body.did)
    except IdentityRegistrationError:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    capture_event(
        status.identity,
        "identity registered",
        {
            "registration_status": status.registration_status,
            "principal_id": status.principal_id or None,
        },
    )
    return status.to_payload()


@router.get("/{handle}")
async def get_identity_status(handle: str, request: Request) -> dict[str, str]:
    status = await request.app.state.identity_bootstrap.get_identity_status(handle=handle)
    if status is None:
        raise HTTPException(status_code=404, detail="Identity not found")
    payload = status.to_payload()
    payload.pop("status", None)
    return payload
