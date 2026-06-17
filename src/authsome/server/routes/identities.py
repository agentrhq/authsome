"""Identity registration routes."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from authsome.identity.principal import ClaimStatus, PrincipalRole
from authsome.server.analytics import capture_event
from authsome.server.credential_service import CredentialService
from authsome.server.routes._deps import get_daemon_or_browser_auth_service
from authsome.server.schemas import AgentDetailResponse
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
        registration_status = await request.app.state.identity_bootstrap.register_identity(
            handle=body.handle, did=body.did
        )
    except IdentityRegistrationError:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    capture_event(
        registration_status.identity,
        "identity registered",
        {
            "registration_status": registration_status.registration_status,
            "principal_id": registration_status.principal_id or None,
        },
    )
    return registration_status.to_payload()


@router.get("/by-did/{did:path}")
async def resolve_identity_by_did(did: str, request: Request) -> dict[str, str]:
    registration = await request.app.state.store.identity_registry.resolve_by_did(did)
    if registration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Identity not found")
    return {"identity": registration.handle, "did": registration.did}


@router.get("/{handle}/detail")
async def get_identity_detail(
    handle: str,
    request: Request,
    auth: CredentialService = Depends(get_daemon_or_browser_auth_service),
) -> AgentDetailResponse:
    registration = await request.app.state.store.identity_registry.resolve(handle)
    if registration is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Identity not found")

    claim = await request.app.state.store.identity_claims.resolve(handle)
    if auth.principal_role != PrincipalRole.ADMIN and (claim is None or claim.principal_id != auth.principal_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Identity not found")

    principal_email = None
    if claim is not None:
        principal = await request.app.state.store.principals.get(claim.principal_id)
        principal_email = principal.email if principal else None

    if claim is None:
        registration_status = "claim_required"
    elif claim.claim_status == ClaimStatus.ACCEPTED:
        registration_status = "claimed"
    else:
        registration_status = claim.claim_status.value

    active_identity = (
        auth.identity or getattr(request.state, "identity", None) or getattr(request.state, "ui_identity", None)
    )
    return AgentDetailResponse(
        handle=registration.handle,
        did=registration.did,
        registration_status=registration_status,
        claim_status=claim.claim_status.value if claim else None,
        principal_id=claim.principal_id if claim else None,
        principal_email=principal_email,
        is_active=registration.handle == active_identity,
        created_at=registration.created_at,
        updated_at=registration.updated_at,
        claimed_at=claim.created_at if claim else None,
    )


@router.get("/{handle}")
async def get_identity_status(handle: str, request: Request) -> dict[str, str]:
    registration_status = await request.app.state.identity_bootstrap.get_identity_status(handle=handle)
    if registration_status is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Identity not found")
    payload = registration_status.to_payload()
    payload.pop("status", None)
    return payload
