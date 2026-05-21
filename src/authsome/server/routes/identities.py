"""Identity registration routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from authsome.server.analytics import capture_event
from authsome.server.registries import IdentityRegistrationError

router = APIRouter(prefix="/identities", tags=["identities"])


class RegisterIdentityRequest(BaseModel):
    handle: str
    did: str


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
