"""Auth session routes."""

from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse, Response

from authsome.auth.input_provider import InputField
from authsome.auth.models.enums import AuthType, FlowType
from authsome.auth.sessions import AuthSession, AuthSessionStatus, AuthSessionStore
from authsome.server.analytics import capture_event
from authsome.server.credential_service import CredentialService
from authsome.server.routes._deps import (
    get_auth_sessions,
    get_protected_auth_service,
    get_server_base_url,
    require_auth_service,
    resolve_ui_request_identity,
    update_device_code_expiry,
)
from authsome.server.schemas import (
    AuthSessionResponse,
    BrowserAction,
    NoneAction,
    OpenUrlAction,
    ResumeAuthSessionRequest,
    StartAuthSessionRequest,
)
from authsome.server.urls import build_auth_input_url, build_auth_success_url, build_callback_url, build_device_url

router = APIRouter(prefix="/auth", tags=["auth"])
browser_router = APIRouter(tags=["auth-ui"], include_in_schema=False)


def _ui_session_required(session: AuthSession) -> bool:
    return bool(session.payload.get("ui_session_required"))


async def _ensure_browser_session_identity(request: Request, session: AuthSession) -> bool:
    if not _ui_session_required(session):
        return True
    await resolve_ui_request_identity(request)
    return getattr(request.state, "ui_principal_id", None) == session.principal_id


async def _load_session_or_404(sessions: AuthSessionStore, session_id: str) -> AuthSession:
    """Return an auth session or raise the route-level not-found response."""
    try:
        return await sessions.get(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Authentication session not found") from exc


def _event_actor(session: AuthSession) -> str:
    return session.identity or session.principal_id or "account-ui"


def _session_event(session: AuthSession, name: str) -> None:
    """Emit a PostHog event describing an auth session transition."""
    capture_event(
        _event_actor(session),
        name,
        {
            "provider": session.provider,
            "flow_type": session.flow_type,
            "principal_id": session.principal_id,
        },
    )


def _mark_completed(session: AuthSession) -> None:
    session.state = AuthSessionStatus.COMPLETED
    session.status_message = "Login successful"
    _session_event(session, "auth session completed")


def _mark_failed(session: AuthSession, error: str) -> None:
    session.state = AuthSessionStatus.FAILED
    session.error_message = error
    _session_event(session, "auth session failed")


@router.post("/sessions", response_model=AuthSessionResponse)
async def start_session(
    body: StartAuthSessionRequest,
    background_tasks: BackgroundTasks,
    auth: CredentialService = Depends(get_protected_auth_service),
    sessions: AuthSessionStore = Depends(get_auth_sessions),
    server_base_url: str = Depends(get_server_base_url),
) -> AuthSessionResponse:
    definition = await auth.get_provider(body.provider)
    flow = FlowType(body.flow) if body.flow else definition.flow
    session = await sessions.create(
        provider=body.provider,
        identity=auth.identity,
        principal_id=auth.principal_id,
        connection_name=body.connection,
        flow_type=flow.value,
    )
    session.payload["force"] = body.force
    session.payload["callback_url_override"] = build_callback_url(server_base_url)
    if body.scopes is not None:
        session.payload["requested_scopes"] = body.scopes
    if body.base_url is not None:
        session.payload["base_url"] = body.base_url

    if not body.force:
        try:
            existing = await auth.get_connection(body.provider, body.connection)
            if auth.has_usable_connection(existing, scopes=body.scopes, base_url=body.base_url):
                session.state = AuthSessionStatus.COMPLETED
                session.status_message = "Already connected"
                await sessions.save(session)
                return _session_response(session, server_base_url)
        except Exception:
            pass

    fields = await auth.get_required_inputs(session, scopes=body.scopes, base_url=body.base_url)
    if fields:
        session.state = AuthSessionStatus.WAITING_FOR_USER
        session.payload["input_fields"] = [_field_to_payload(field) for field in fields]
        await sessions.save(session)
        return _session_response(session, server_base_url)

    await auth.begin_login_flow(
        session=session,
        scopes=body.scopes,
        force=body.force,
        base_url=body.base_url,
    )
    if FlowType(session.flow_type) == FlowType.DEVICE_CODE:
        update_device_code_expiry(session)
        background_tasks.add_task(auth.background_resume, session)
    await sessions.index_oauth_state(session)
    _session_event(session, "auth session started")
    return _session_response(session, server_base_url)


@router.get("/sessions/{session_id}", response_model=AuthSessionResponse)
async def get_session(
    session_id: str,
    auth: CredentialService = Depends(get_protected_auth_service),
    sessions: AuthSessionStore = Depends(get_auth_sessions),
    server_base_url: str = Depends(get_server_base_url),
) -> AuthSessionResponse:
    session = await _load_session_or_404(sessions, session_id)
    if session.identity != auth.identity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Authentication session not found")
    return _session_response(session, server_base_url)


@router.post("/sessions/{session_id}/resume", response_model=AuthSessionResponse)
async def resume_session(
    session_id: str,
    body: ResumeAuthSessionRequest,
    auth: CredentialService = Depends(get_protected_auth_service),
    sessions: AuthSessionStore = Depends(get_auth_sessions),
    server_base_url: str = Depends(get_server_base_url),
) -> AuthSessionResponse:
    session = await _load_session_or_404(sessions, session_id)
    if session.identity != auth.identity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Authentication session not found")
    try:
        record = await auth.resume_login_flow(session, body.data)
        if record is None:
            session.state = AuthSessionStatus.WAITING_FOR_USER
        else:
            _mark_completed(session)
        await sessions.save(session)
    except Exception as exc:
        _mark_failed(session, str(exc))
        await sessions.save(session)
        raise
    return _session_response(session, server_base_url)


@router.get("/callback/oauth")
async def oauth_callback(
    request: Request,
    sessions: AuthSessionStore = Depends(get_auth_sessions),
    server_base_url: str = Depends(get_server_base_url),
) -> Response:
    state = request.query_params.get("state")
    if not state:
        return RedirectResponse("/auth/success?error=missing_state", status_code=status.HTTP_303_SEE_OTHER)
    try:
        session = await sessions.get_by_oauth_state(state)
    except KeyError:
        return RedirectResponse("/auth/success?error=session_expired", status_code=status.HTTP_303_SEE_OTHER)
    if not await _ensure_browser_session_identity(request, session):
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    callback_data = dict(request.query_params)
    auth = await require_auth_service(
        request,
        identity=session.identity,
        principal_id=session.principal_id,
        detail="Authentication session not found",
    )
    try:
        await auth.resume_login_flow(session, callback_data)
        _mark_completed(session)
        await sessions.save(session)
    except Exception as exc:
        _mark_failed(session, str(exc))
        await sessions.save(session)
        return RedirectResponse(
            build_auth_success_url(server_base_url, session.session_id), status_code=status.HTTP_303_SEE_OTHER
        )
    if return_url := session.payload.get("return_url"):
        return RedirectResponse(str(return_url), status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(
        build_auth_success_url(server_base_url, session.session_id), status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/sessions/{session_id}/input")
async def get_session_input(
    session_id: str,
    request: Request,
    sessions: AuthSessionStore = Depends(get_auth_sessions),
    server_base_url: str = Depends(get_server_base_url),
) -> Any:
    try:
        session = await sessions.get(session_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Authentication session not found") from None
    if not await _ensure_browser_session_identity(request, session):
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    auth = await require_auth_service(
        request,
        identity=session.identity,
        principal_id=session.principal_id,
        detail="Authentication session not found",
    )
    definition = await auth.get_provider(session.provider)
    fields = session.payload.get("input_fields", [])

    callback_url = None
    if definition.auth_type == AuthType.OAUTH2:
        callback_url = build_callback_url(server_base_url)

    return {
        "session_id": session.session_id,
        "provider": session.provider,
        "display_name": definition.display_name,
        "docs_url": definition.docs_url,
        "fields": fields,
        "callback_url": callback_url,
        "warning": None,
    }


@router.get("/sessions/{session_id}/device")
async def get_session_device_code(
    session_id: str,
    request: Request,
    sessions: AuthSessionStore = Depends(get_auth_sessions),
) -> Any:
    try:
        session = await sessions.get(session_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Authentication session not found") from None
    if not await _ensure_browser_session_identity(request, session):
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    user_code = session.payload.get("user_code")
    verification_uri = session.payload.get("verification_uri")
    verification_uri_complete = session.payload.get("verification_uri_complete")
    if not user_code or not verification_uri:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This session does not have a device code")
    auth = await require_auth_service(
        request,
        identity=session.identity,
        principal_id=session.principal_id,
        detail="Authentication session not found",
    )
    definition = await auth.get_provider(session.provider)
    return {
        "session_id": session.session_id,
        "display_name": definition.display_name,
        "user_code": user_code,
        "verification_uri": verification_uri,
        "verification_uri_complete": verification_uri_complete,
    }


@router.get("/sessions/{session_id}/status")
async def get_browser_session_status(
    session_id: str,
    request: Request,
    sessions: AuthSessionStore = Depends(get_auth_sessions),
) -> Any:
    try:
        session = await sessions.get(session_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Authentication session not found") from None
    if not await _ensure_browser_session_identity(request, session):
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    return {
        "id": session.session_id,
        "provider": session.provider,
        "connection": session.connection_name,
        "status": session.state,
        "message": session.status_message,
        "error": session.error_message,
    }


@router.post("/sessions/{session_id}/input")
async def submit_input(
    session_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    sessions: AuthSessionStore = Depends(get_auth_sessions),
    server_base_url: str = Depends(get_server_base_url),
):
    return await _submit_session_input(
        session_id=session_id,
        request=request,
        background_tasks=background_tasks,
        sessions=sessions,
        server_base_url=server_base_url,
    )


@browser_router.post("/auth/input")
async def submit_browser_input(
    request: Request,
    background_tasks: BackgroundTasks,
    session: str,
    sessions: AuthSessionStore = Depends(get_auth_sessions),
    server_base_url: str = Depends(get_server_base_url),
):
    return await _submit_session_input(
        session_id=session,
        request=request,
        background_tasks=background_tasks,
        sessions=sessions,
        server_base_url=server_base_url,
    )


async def _submit_session_input(  # noqa: PLR0911
    *,
    session_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    sessions: AuthSessionStore,
    server_base_url: str,
):
    try:
        session = await sessions.get(session_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Authentication session not found") from None
    if not await _ensure_browser_session_identity(request, session):
        return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
    auth = await require_auth_service(
        request,
        identity=session.identity,
        principal_id=session.principal_id,
        detail="Authentication session not found",
    )
    form = await request.form()
    inputs = {key: str(value) for key, value in form.items()}

    await auth.save_inputs(session, inputs)

    flow = FlowType(session.flow_type)
    if flow == FlowType.API_KEY:
        await auth.resume_login_flow(session, {})
        _mark_completed(session)
        await sessions.save(session)
        if return_url := session.payload.get("return_url"):
            return RedirectResponse(str(return_url), status_code=status.HTTP_303_SEE_OTHER)
        return RedirectResponse(
            build_auth_success_url(server_base_url, session.session_id), status_code=status.HTTP_303_SEE_OTHER
        )

    session.payload["callback_url_override"] = build_callback_url(server_base_url)
    await auth.begin_login_flow(
        session=session,
        scopes=session.payload.get("requested_scopes"),
        force=bool(session.payload.get("force", False)),
        base_url=session.payload.get("base_url"),
    )
    if flow == FlowType.DEVICE_CODE:
        update_device_code_expiry(session)
        background_tasks.add_task(auth.background_resume, session)
        if session.payload.get("user_code") and session.payload.get("verification_uri"):
            await sessions.save(session)
            return RedirectResponse(
                url=build_device_url(server_base_url, session.session_id), status_code=status.HTTP_303_SEE_OTHER
            )

    await sessions.index_oauth_state(session)

    auth_url = session.payload.get("auth_url")
    if auth_url:
        await sessions.save(session)
        return RedirectResponse(str(auth_url), status_code=status.HTTP_303_SEE_OTHER)
    await sessions.save(session)
    return RedirectResponse(
        build_auth_success_url(server_base_url, session.session_id), status_code=status.HTTP_303_SEE_OTHER
    )


def _session_response(session: AuthSession, server_base_url: str) -> AuthSessionResponse:
    action: OpenUrlAction | BrowserAction | NoneAction = NoneAction()
    input_fields = session.payload.get("input_fields")
    if input_fields and session.state != AuthSessionStatus.COMPLETED:
        action = OpenUrlAction(type="open_url", url=build_auth_input_url(server_base_url, session.session_id))
    elif session.payload.get("browser_login") and session.state != AuthSessionStatus.COMPLETED:
        action = BrowserAction(
            entry_url=str(session.payload["entry_url"]),
            domains=session.payload.get("domains", []),
            auth_cookies=session.payload.get("auth_cookies", []),
            ttl_from_cookie=session.payload.get("ttl_from_cookie"),
            ttl_hours=int(session.payload.get("ttl_hours", 24)),
        )
    elif session.payload.get("auth_url"):
        action = OpenUrlAction(type="open_url", url=str(session.payload["auth_url"]))
    elif session.payload.get("verification_uri") and session.payload.get("user_code"):
        action = OpenUrlAction(
            type="open_url",
            url=build_device_url(server_base_url, session.session_id),
        )
    return AuthSessionResponse(
        id=session.session_id,
        provider=session.provider,
        connection=session.connection_name,
        status=session.state,
        message=session.status_message,
        error=session.error_message,
        created_at=session.created_at,
        expires_at=session.expires_at,
        next_action=action,
        user_code=session.payload.get("user_code"),
        verification_uri=session.payload.get("verification_uri"),
        verification_uri_complete=session.payload.get("verification_uri_complete"),
    )


def _field_to_payload(field: InputField) -> dict[str, Any]:
    return field.model_dump(mode="json", exclude_none=True)
