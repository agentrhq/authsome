"""Browser-session routes for the Authsome local dashboard."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from fastapi.responses import RedirectResponse

from authsome.auth.models.enums import FlowType
from authsome.auth.sessions import AuthSessionStore
from authsome.server.analytics import capture_event
from authsome.server.credential_service import CredentialService
from authsome.server.routes._deps import (
    UI_SESSION_COOKIE_NAME,
    get_auth_service,
    get_auth_sessions,
    get_protected_auth_service,
    get_server_base_url,
    get_ui_sessions,
    resolve_ui_request_identity,
    update_device_code_expiry,
)
from authsome.server.schemas import UiBootstrapResponse
from authsome.server.ui_sessions import UiSessionStore
from authsome.server.urls import build_auth_input_url, build_callback_url, build_device_url

router = APIRouter(tags=["ui"], include_in_schema=False)


def _redirect(request: Request, url: str) -> Response:
    """Redirect normally, or via htmx full-page redirect for form compatibility."""
    if request.headers.get("HX-Request") == "true":
        return Response(status_code=204, headers={"HX-Redirect": url})
    return RedirectResponse(url=url, status_code=303)


class UiAuthRequiredError(Exception):
    """Raised when a UI route needs to return an auth-related response."""

    def __init__(self, response: Response) -> None:
        self.response = response


async def _resolve_ui_auth(request: Request, *, next_url: str | None = None) -> CredentialService:
    identity = await resolve_ui_request_identity(request)
    auth = await get_auth_service(
        request,
        identity=identity,
        principal_id=getattr(request.state, "ui_principal_id", None),
    )
    if auth is not None:
        return auth

    target = _account_auth_next_url(next_url or request.query_params.get("next") or request.url.path)
    raise UiAuthRequiredError(RedirectResponse(url=_account_auth_entry_url(target), status_code=303))


def require_ui_auth(next_url: str | None = None) -> Callable[[Request], Awaitable[CredentialService]]:
    async def dependency(request: Request) -> CredentialService:
        return await _resolve_ui_auth(request, next_url=next_url)

    return dependency


def _account_auth_entry_url(next_url: str = "/") -> str:
    return f"/login?{urlencode({'next': _account_auth_next_url(next_url)})}"


def _ui_cookie_secure(server_base_url: str) -> bool:
    return server_base_url.startswith("https://")


def _set_ui_session_cookie(
    response: Response,
    token: str,
    ui_sessions: UiSessionStore,
    server_base_url: str,
) -> None:
    response.set_cookie(
        UI_SESSION_COOKIE_NAME,
        ui_sessions.build_cookie_value(token),
        httponly=True,
        secure=_ui_cookie_secure(server_base_url),
        samesite="lax",
        path="/",
    )


def _clear_ui_session_cookie(response: Response) -> None:
    response.delete_cookie(UI_SESSION_COOKIE_NAME, path="/")


def _account_auth_next_url(value: Any) -> str:
    next_url = str(value or "/").strip() or "/"
    if not next_url.startswith("/") or next_url.startswith("//"):
        return "/"
    return next_url


@router.post("/auth/providers/{provider_name}/connect", include_in_schema=False)
async def connect_provider(
    provider_name: str,
    request: Request,
    background_tasks: BackgroundTasks,
    auth: CredentialService = Depends(require_ui_auth("/")),
    sessions: AuthSessionStore = Depends(get_auth_sessions),
    server_base_url: str = Depends(get_server_base_url),
) -> Response:
    """Start a provider connection from the static dashboard."""
    form = await request.form()
    connection_name = str(form.get("connection") or form.get("connection_name") or "default")
    force = str(form.get("force", "false")).lower() in {"1", "true", "on", "yes"}
    return_path = _account_auth_next_url(form.get("return_url") or "/")

    definition = await auth.get_provider(provider_name)
    flow = definition.flow
    session = await sessions.create(
        provider=provider_name,
        identity=auth.identity,
        principal_id=auth.principal_id,
        connection_name=connection_name,
        flow_type=flow.value,
    )
    session.payload["force"] = force
    session.payload["callback_url_override"] = build_callback_url(server_base_url)
    session.payload["return_url"] = f"{server_base_url.rstrip('/')}{return_path}"
    session.payload["ui_session_required"] = True

    if not force:
        try:
            existing = await auth.get_connection(provider_name, connection_name)
            if auth.has_usable_connection(existing):
                session.status_message = "Already connected"
                await sessions.save(session)
                return _redirect(request, return_path)
        except Exception:
            pass

    fields = await auth.get_required_inputs(session)
    if fields:
        session.payload["input_fields"] = [field.model_dump(mode="json", exclude_none=True) for field in fields]
        await sessions.save(session)
        return _redirect(request, build_auth_input_url(server_base_url, session.session_id))

    await auth.begin_login_flow(session=session, force=force)
    if flow == FlowType.DEVICE_CODE:
        update_device_code_expiry(session)
        background_tasks.add_task(auth.background_resume, session)
        if session.payload.get("user_code") and session.payload.get("verification_uri"):
            await sessions.save(session)
            return _redirect(request, build_device_url(server_base_url, session.session_id))

    await sessions.index_oauth_state(session)
    auth_url = session.payload.get("auth_url")
    if auth_url:
        await sessions.save(session)
        return _redirect(request, str(auth_url))
    await sessions.save(session)
    return _redirect(request, return_path)


@router.post("/session", response_model=UiBootstrapResponse)
async def start_ui_session(
    auth: CredentialService = Depends(get_protected_auth_service),
    server_base_url: str = Depends(get_server_base_url),
) -> UiBootstrapResponse:
    """Return a browser URL for opening the dashboard."""
    _ = auth
    return UiBootstrapResponse(url=f"{server_base_url.rstrip('/')}/")


@router.post("/logout")
async def logout_ui_session(
    request: Request,
    ui_sessions: UiSessionStore = Depends(get_ui_sessions),
) -> Response:
    """Clear the dashboard browser session."""
    form = await request.form()
    response = _redirect(request, _account_auth_next_url(form.get("return_url") or "/"))
    cookie_value = request.cookies.get(UI_SESSION_COOKIE_NAME)
    if cookie_value:
        try:
            browser_session = ui_sessions.get_browser_session(cookie_value)
            capture_event(
                browser_session.email,
                "account_logged_out",
                {"principal_id": browser_session.principal_id},
            )
        except KeyError:
            pass
        try:
            ui_sessions.delete_browser_session(cookie_value)
        except KeyError:
            pass
    _clear_ui_session_cookie(response)
    return response


@router.get("/claim/{token}", include_in_schema=False)
async def claim_identity_page(
    token: str,
    request: Request,
    ui_sessions: UiSessionStore = Depends(get_ui_sessions),
) -> dict[str, str | bool]:
    try:
        pending = ui_sessions.get_pending_claim(token)
    except KeyError:
        return {"token": token, "identity": "", "authenticated": False, "expired": True}

    await resolve_ui_request_identity(request)
    return {
        "token": token,
        "identity": pending.identity,
        "authenticated": getattr(request.state, "ui_principal_id", None) is not None,
        "email": getattr(request.state, "ui_email", None) or "",
        "expired": False,
    }


@router.post("/auth/register", include_in_schema=False)
async def register_account(
    request: Request,
    ui_sessions: UiSessionStore = Depends(get_ui_sessions),
    server_base_url: str = Depends(get_server_base_url),
) -> Response:
    form = await request.form()
    email = str(form.get("email", "")).strip()
    password = str(form.get("password", ""))
    next_url = _account_auth_next_url(form.get("next"))

    try:
        session = await request.app.state.account_auth_service.register_and_login(email=email, password=password)
    except ValueError as exc:
        return RedirectResponse(
            url=f"/login?{urlencode({'next': next_url, 'error': str(exc), 'tab': 'register'})}",
            status_code=303,
        )

    capture_event(session.email, "account_registered", {"principal_id": session.principal_id})
    response = RedirectResponse(url=next_url, status_code=303)
    _set_ui_session_cookie(response, session.token, ui_sessions, server_base_url)
    return response


@router.post("/auth/login", include_in_schema=False)
async def login_account(
    request: Request,
    ui_sessions: UiSessionStore = Depends(get_ui_sessions),
    server_base_url: str = Depends(get_server_base_url),
) -> Response:
    form = await request.form()
    email = str(form.get("email", "")).strip()
    password = str(form.get("password", ""))
    next_url = _account_auth_next_url(form.get("next"))

    try:
        session = await request.app.state.account_auth_service.login(email=email, password=password)
    except ValueError as exc:
        return RedirectResponse(
            url=f"/login?{urlencode({'next': next_url, 'error': str(exc), 'tab': 'login'})}",
            status_code=303,
        )

    capture_event(session.email, "account_logged_in", {"principal_id": session.principal_id})
    response = RedirectResponse(url=next_url, status_code=303)
    _set_ui_session_cookie(response, session.token, ui_sessions, server_base_url)
    return response


@router.post("/claim/{token}/confirm", include_in_schema=False)
async def claim_identity_confirm(
    token: str,
    request: Request,
    ui_sessions: UiSessionStore = Depends(get_ui_sessions),
) -> Response:
    try:
        pending = ui_sessions.get_pending_claim(token)
    except KeyError:
        return RedirectResponse(url=f"/claim?{urlencode({'token': token, 'error': 'expired'})}", status_code=303)

    await resolve_ui_request_identity(request)
    principal_id = getattr(request.state, "ui_principal_id", None)
    if not principal_id:
        return RedirectResponse(url=f"/login?{urlencode({'next': f'/claim?token={token}'})}", status_code=303)

    pending = ui_sessions.consume_pending_claim(token)
    await request.app.state.ownership_resolver.claim_identity_for_principal(
        identity=pending.identity,
        principal_id=principal_id,
    )
    request.app.state.ownership_cache.pop(pending.identity, None)
    capture_event(pending.identity, "identity_claimed", {"principal_id": principal_id})
    return RedirectResponse(url="/", status_code=303)
