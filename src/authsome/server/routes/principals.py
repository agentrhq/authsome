"""Principal listing routes (admin only)."""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from authsome.identity.principal import PrincipalRole
from authsome.server.credential_service import CredentialService
from authsome.server.routes._deps import get_daemon_or_browser_auth_service

router = APIRouter(prefix="/principals", tags=["principals"])


@router.get("")
@router.get("/")
async def list_principals(
    request: Request,
    auth: CredentialService = Depends(get_daemon_or_browser_auth_service),
) -> dict:
    if auth.principal_role != PrincipalRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    principals = await request.app.state.store.principals.list_all()
    return {
        "principals": [
            {
                "principal_id": p.principal_id,
                "email": p.email,
                "role": p.role.value,
                "created_at": p.created_at.isoformat(),
            }
            for p in principals
        ]
    }
