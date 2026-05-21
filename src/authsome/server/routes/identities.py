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
        status = await request.app.state.identity_bootstrap.register_identity(handle=body.handle, did=body.did)
    except IdentityRegistrationError:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    ph = get_posthog()
    if ph is not None:
        from posthog import identify_context, new_context

        with new_context():
            identify_context(status.identity)
            ph.capture(
                "identity registered",
                distinct_id=status.identity,
                properties={
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
