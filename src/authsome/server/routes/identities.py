"""Identity registration routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from authsome.identity.registry import IdentityRegistrationError
from authsome.server.analytics import get_posthog

router = APIRouter(prefix="/identities", tags=["identities"])


class RegisterIdentityRequest(BaseModel):
    handle: str
    did: str


@router.post("/register")
async def register_identity(body: RegisterIdentityRequest, request: Request) -> dict[str, str]:
    try:
        registration = await request.app.state.identity_registry.register(handle=body.handle, did=body.did)
    except IdentityRegistrationError:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    ph = get_posthog()
    if ph is not None:
        from posthog import identify_context, new_context

        with new_context():
            identify_context(registration.handle)
            ph.capture("identity registered", distinct_id=registration.handle)
    return {
        "status": "registered",
        "identity": registration.handle,
        "did": registration.did,
    }
