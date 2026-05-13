"""Identity registration routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from authsome.identity.registry import IdentityRegistrationError

router = APIRouter(prefix="/identities", tags=["identities"])


class RegisterIdentityRequest(BaseModel):
    handle: str
    did: str


@router.post("/register")
async def register_identity(body: RegisterIdentityRequest, request: Request) -> dict[str, str]:
    try:
        registration = request.app.state.identity_registry.register(handle=body.handle, did=body.did)
    except IdentityRegistrationError:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "status": "registered",
        "identity": registration.handle,
        "did": registration.did,
    }
