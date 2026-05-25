"""Auth session routes and browser input pages."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from authsome.auth.input_provider import InputField
from authsome.auth.models.enums import AuthType, FlowType
from authsome.auth.sessions import AuthSession, AuthSessionStatus, AuthSessionStore
from authsome.server.analytics import capture_event
from authsome.server.credential_service import AuthService
from authsome.server.routes._deps import (
    get_auth_sessions,
    get_protected_auth_service,
    get_server_base_url,
    require_auth_service,
    resolve_ui_request_identity,
)
from authsome.server.schemas import (
    AuthSessionResponse,
    NoneAction,
    OpenUrlAction,
    ResumeAuthSessionRequest,
    StartAuthSessionRequest,
)
from authsome.server.ui import pages
from authsome.server.urls import build_auth_input_url, build_callback_url, build_device_url
from authsome.utils import utc_now

router = APIRouter(prefix="/auth", tags=["auth"])


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
        raise HTTPException(status_code=404, detail="Authentication session not found") from exc


def _event_actor(session: AuthSession) -> str:
    return session.identity or session.principal_id or "hosted-ui"


@router.post("/sessions", response_model=AuthSessionResponse)
async def start_session(
    body: StartAuthSessionRequest,
    background_tasks: BackgroundTasks,
    auth: AuthService = Depends(get_protected_auth_service),
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
            if auth._connection_is_valid(existing) and auth._requested_context_matches(
                existing,
                scopes=body.scopes,
                base_url=body.base_url,
            ):
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
        _update_device_code_expiry(sessions, session)
        background_tasks.add_task(auth.background_resume, session)
    await sessions.index_oauth_state(session)
    capture_event(
        _event_actor(session),
        "auth session started",
        {
            "provider": session.provider,
            "flow_type": session.flow_type,
            "principal_id": session.principal_id,
        },
    )
    return _session_response(session, server_base_url)


@router.get("/sessions/{session_id}", response_model=AuthSessionResponse)
async def get_session(
    session_id: str,
    auth: AuthService = Depends(get_protected_auth_service),
    sessions: AuthSessionStore = Depends(get_auth_sessions),
    server_base_url: str = Depends(get_server_base_url),
) -> AuthSessionResponse:
    session = await _load_session_or_404(sessions, session_id)
    if session.identity != auth.identity:
        raise HTTPException(status_code=404, detail="Authentication session not found")
    return _session_response(session, server_base_url)


@router.post("/sessions/{session_id}/resume", response_model=AuthSessionResponse)
async def resume_session(
    session_id: str,
    body: ResumeAuthSessionRequest,
    auth: AuthService = Depends(get_protected_auth_service),
    sessions: AuthSessionStore = Depends(get_auth_sessions),
    server_base_url: str = Depends(get_server_base_url),
) -> AuthSessionResponse:
    session = await _load_session_or_404(sessions, session_id)
    if session.identity != auth.identity:
        raise HTTPException(status_code=404, detail="Authentication session not found")
    try:
        record = await auth.resume_login_flow(session, body.data)
        if record is None:
            session.state = AuthSessionStatus.WAITING_FOR_USER
        else:
            session.state = AuthSessionStatus.COMPLETED
            session.status_message = "Login successful"
            capture_event(
                _event_actor(session),
                "auth session completed",
                {
                    "provider": session.provider,
                    "flow_type": session.flow_type,
                    "principal_id": session.principal_id,
                },
            )
        await sessions.save(session)
    except Exception as exc:
        session.state = AuthSessionStatus.FAILED
        session.error_message = str(exc)
        await sessions.save(session)
        capture_event(
            _event_actor(session),
            "auth session failed",
            {
                "provider": session.provider,
                "flow_type": session.flow_type,
                "principal_id": session.principal_id,
            },
        )
        raise
    return _session_response(session, server_base_url)


@router.get("/callback/oauth", response_class=HTMLResponse)
async def oauth_callback(
    request: Request,
    sessions: AuthSessionStore = Depends(get_auth_sessions),
) -> Response:
    state = request.query_params.get("state")
    if not state:
        return HTMLResponse(pages.message_page("Authentication failed", "Missing OAuth state."), status_code=400)
    try:
        session = await sessions.get_by_oauth_state(state)
    except KeyError:
        return HTMLResponse(
            pages.message_page("Authentication session expired", "Please run authsome login again."),
            status_code=400,
        )
    if not await _ensure_browser_session_identity(request, session):
        return HTMLResponse(
            pages.message_page("Dashboard session expired", "Run 'authsome ui' to reopen the hosted dashboard."),
            status_code=401,
        )
    callback_data = dict(request.query_params)
    auth = await require_auth_service(
        request,
        identity=session.identity,
        principal_id=session.principal_id,
        detail="Authentication session not found",
    )
    try:
        await auth.resume_login_flow(session, callback_data)
        session.state = AuthSessionStatus.COMPLETED
        session.status_message = "Login successful"
        await sessions.save(session)
        capture_event(
            _event_actor(session),
            "auth session completed",
            {
                "provider": session.provider,
                "flow_type": session.flow_type,
                "principal_id": session.principal_id,
            },
        )
    except Exception as exc:
        session.state = AuthSessionStatus.FAILED
        session.error_message = str(exc)
        await sessions.save(session)
        capture_event(
            _event_actor(session),
            "auth session failed",
            {
                "provider": session.provider,
                "flow_type": session.flow_type,
                "principal_id": session.principal_id,
            },
        )
        return HTMLResponse(pages.message_page("Authentication failed", str(exc)), status_code=400)
    if return_url := session.payload.get("return_url"):
        return RedirectResponse(str(return_url), status_code=303)
    return HTMLResponse(pages.message_page("Authentication successful", "You can close this window."))


@router.get("/sessions/{session_id}/input", response_class=HTMLResponse)
async def input_page(
    session_id: str,
    request: Request,
    sessions: AuthSessionStore = Depends(get_auth_sessions),
    server_base_url: str = Depends(get_server_base_url),
) -> HTMLResponse:
    try:
        session = await sessions.get(session_id)
    except KeyError:
        return HTMLResponse(
            pages.message_page("Authentication session expired", "Please run authsome login again."),
            status_code=404,
        )
    if not await _ensure_browser_session_identity(request, session):
        return HTMLResponse(
            pages.message_page("Dashboard session expired", "Run 'authsome ui' to reopen the hosted dashboard."),
            status_code=401,
        )
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
    warning_message = None
    if session.payload.get("provider_config_only") and session.payload.get("existing_provider_client"):
        warning_message = "Changing these credentials will revoke existing connections for this provider."

    return HTMLResponse(
        pages.input_page(
            session.session_id,
            definition.display_name,
            definition.docs_url,
            fields,
            callback_url=callback_url,
            warning_message=warning_message,
        )
    )


@router.get("/sessions/{session_id}/device", response_class=HTMLResponse)
async def device_page(
    session_id: str,
    request: Request,
    sessions: AuthSessionStore = Depends(get_auth_sessions),
) -> HTMLResponse:
    try:
        session = await sessions.get(session_id)
    except KeyError:
        return HTMLResponse(
            pages.message_page("Authentication session expired", "Please run authsome login again."),
            status_code=404,
        )
    if not await _ensure_browser_session_identity(request, session):
        return HTMLResponse(
            pages.message_page("Dashboard session expired", "Run 'authsome ui' to reopen the hosted dashboard."),
            status_code=401,
        )
    user_code = session.payload.get("user_code")
    verification_uri = session.payload.get("verification_uri")
    verification_uri_complete = session.payload.get("verification_uri_complete")
    if not user_code or not verification_uri:
        return HTMLResponse(
            pages.message_page("Invalid session", "This session does not have a device code."), status_code=400
        )
    auth = await require_auth_service(
        request,
        identity=session.identity,
        principal_id=session.principal_id,
        detail="Authentication session not found",
    )
    definition = await auth.get_provider(session.provider)
    return HTMLResponse(
        pages.device_code_page(definition.display_name, user_code, verification_uri, verification_uri_complete)
    )


@router.post("/sessions/{session_id}/input")
async def submit_input(
    session_id: str,
    request: Request,
    background_tasks: BackgroundTasks,
    sessions: AuthSessionStore = Depends(get_auth_sessions),
    server_base_url: str = Depends(get_server_base_url),
):
    try:
        session = await sessions.get(session_id)
    except KeyError:
        return HTMLResponse(
            pages.message_page("Authentication session expired", "Please run authsome login again."),
            status_code=404,
        )
    if not await _ensure_browser_session_identity(request, session):
        return HTMLResponse(
            pages.message_page("Dashboard session expired", "Run 'authsome ui' to reopen the hosted dashboard."),
            status_code=401,
        )
    auth = await require_auth_service(
        request,
        identity=session.identity,
        principal_id=session.principal_id,
        detail="Authentication session not found",
    )
    form = await request.form()
    inputs = {key: str(value) for key, value in form.items()}

    if session.payload.get("provider_config_only"):
        all_vaults = await request.app.state.vault_registry.list_all()
        vault_ids = [vault.vault_id for vault in all_vaults] or ([auth.vault_id] if auth.vault_id else [])
        await auth.update_provider_configuration(session.provider, inputs, vault_ids=vault_ids)
        session.state = AuthSessionStatus.COMPLETED
        session.status_message = "Provider configuration updated"
        await sessions.save(session)
        if return_url := session.payload.get("return_url"):
            return RedirectResponse(str(return_url), status_code=303)
        return HTMLResponse(pages.message_page("Provider configuration updated", "You can close this window."))

    await auth.save_inputs(session, inputs)

    flow = FlowType(session.flow_type)
    if flow == FlowType.API_KEY:
        await auth.resume_login_flow(session, {})
        session.state = AuthSessionStatus.COMPLETED
        session.status_message = "Login successful"
        await sessions.save(session)
        capture_event(
            _event_actor(session),
            "auth session completed",
            {
                "provider": session.provider,
                "flow_type": session.flow_type,
                "principal_id": session.principal_id,
            },
        )
        if return_url := session.payload.get("return_url"):
            return RedirectResponse(str(return_url), status_code=303)
        return HTMLResponse(pages.message_page("Authentication successful", "You can close this window."))

    session.payload["callback_url_override"] = build_callback_url(server_base_url)
    await auth.begin_login_flow(
        session=session,
        scopes=session.payload.get("requested_scopes"),
        force=bool(session.payload.get("force", False)),
        base_url=session.payload.get("base_url"),
    )
    if flow == FlowType.DEVICE_CODE:
        _update_device_code_expiry(sessions, session)
        background_tasks.add_task(auth.background_resume, session)
        if session.payload.get("user_code") and session.payload.get("verification_uri"):
            await sessions.save(session)
            return RedirectResponse(url=build_device_url(server_base_url, session.session_id), status_code=303)

    await sessions.index_oauth_state(session)

    auth_url = session.payload.get("auth_url")
    if auth_url:
        await sessions.save(session)
        return RedirectResponse(str(auth_url), status_code=303)
    await sessions.save(session)
    return HTMLResponse(pages.message_page("Authentication started", "Return to your terminal to continue."))


def _update_device_code_expiry(sessions: AuthSessionStore, session: AuthSession) -> None:
    if "expires_in" in session.payload:
        try:
            session.expires_at = utc_now() + timedelta(seconds=int(session.payload["expires_in"]))
        except ValueError:
            pass


def _session_response(session: AuthSession, server_base_url: str) -> AuthSessionResponse:
    action: OpenUrlAction | NoneAction = NoneAction()
    input_fields = session.payload.get("input_fields")
    if input_fields and session.state != AuthSessionStatus.COMPLETED:
        action = OpenUrlAction(type="open_url", url=build_auth_input_url(server_base_url, session.session_id))
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
    )


def _field_to_payload(field: InputField) -> dict[str, Any]:
    return field.model_dump(mode="json", exclude_none=True)
