"""Audit event routes."""

from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status

from authsome import audit
from authsome.identity.principal import PrincipalRole
from authsome.server.credential_service import CredentialService
from authsome.server.routes._deps import (
    get_daemon_or_browser_auth_service,
    get_protected_auth_service,
)

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events")
async def list_audit_events(
    request: Request,
    limit: int = 50,
    cursor: str | None = None,
    identity: str | None = None,
    auth: CredentialService = Depends(get_daemon_or_browser_auth_service),
) -> dict[str, Any]:
    effective_principal_id = None if auth.principal_role == PrincipalRole.ADMIN else auth.principal_id
    scope: Literal["global", "principal"] = "global" if effective_principal_id is None else "principal"
    try:
        page = await request.app.state.audit_log.query_events(
            limit=limit,
            principal_id=effective_principal_id,
            identity=identity,
            cursor=cursor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return {"entries": page.entries, "next_cursor": page.next_cursor, "scope": scope}


@router.post("/events")
async def record_external_audit_event(
    body: dict[str, Any],
    auth: CredentialService = Depends(get_protected_auth_service),
) -> dict[str, str]:
    event_payload = body.get("event", body)
    event = audit.AuditEvent.model_validate(event_payload).model_copy(
        update={
            "source": "external",
            "identity": auth.identity,
            "principal_id": auth.principal_id,
        }
    )
    audit.emit(event)
    return {"status": "ok", "event_id": event.event_id}
