"""Audit event routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request

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
    auth: CredentialService = Depends(get_daemon_or_browser_auth_service),
) -> dict[str, Any]:
    principal_id = None if auth.principal_role == PrincipalRole.ADMIN else auth.principal_id
    return {"entries": await request.app.state.audit_log.list_events(limit=limit, principal_id=principal_id)}


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
