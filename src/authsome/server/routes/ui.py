"""HTML routes that render the Authsome local dashboard.

The UI is intentionally server-rendered against the same FastAPI app that
serves the JSON daemon API. This keeps it a single process on port 7998
and avoids a separate static server.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from importlib.resources import files
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from authsome import __version__
from authsome.auth import AuthService
from authsome.auth.models.enums import AuthType, FlowType
from authsome.auth.models.provider import ProviderDefinition
from authsome.auth.sessions import AuthSession, AuthSessionStore
from authsome.errors import ConnectionNotFoundError
from authsome.server.dependencies import get_deployment_mode
from authsome.server.routes._deps import (
    UI_SESSION_COOKIE_NAME,
    get_auth_service_for_identity,
    get_auth_sessions,
    get_protected_auth_service,
    get_server_base_url,
    get_ui_sessions,
    resolve_ui_request_identity,
)
from authsome.server.schemas import UiBootstrapResponse
from authsome.server.ui import pages
from authsome.server.ui_sessions import UiSessionStore
from authsome.server.urls import build_auth_input_url, build_callback_url, build_device_url
from authsome.utils import utc_now

router = APIRouter(prefix="/ui", tags=["ui"], include_in_schema=False)

# Templates ship inside the installed package alongside the code.
_TEMPLATES_DIR = files("authsome.ui").joinpath("templates")
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def _redirect(request: Request, url: str) -> Response:
    """Redirect normally, or via htmx full-page redirect for boosted forms."""
    if request.headers.get("HX-Request") == "true":
        return Response(status_code=204, headers={"HX-Redirect": url})
    return RedirectResponse(url=url, status_code=303)


def _update_device_code_expiry(sessions: AuthSessionStore, session: AuthSession) -> None:
    if "expires_in" not in session.payload:
        return
    try:
        session.expires_at = utc_now() + timedelta(seconds=int(session.payload["expires_in"]))
    except ValueError:
        pass


def _field_payloads(session: AuthSession) -> list[dict[str, Any]]:
    fields = session.payload.get("input_fields", [])
    return [dict(field) for field in fields]


def _is_hosted_ui() -> bool:
    return get_deployment_mode() == "hosted"


def _ui_cookie_secure(server_base_url: str) -> bool:
    return server_base_url.startswith("https://")


def _ui_policy() -> dict[str, Any]:
    hosted = _is_hosted_ui()
    return {
        "ui_mode": "hosted" if hosted else "local",
        "show_provider_client_details": not hosted,
        "provider_management_label": "OAuth application managed by Authsome" if hosted else "OAuth Application",
        "show_hosted_identity": hosted,
    }


async def _resolve_ui_auth(request: Request) -> AuthService | None:
    identity = await resolve_ui_request_identity(request)
    if not identity:
        return None
    return await get_auth_service_for_identity(request, identity)


def _ui_session_expired_response(status_code: int = 401) -> HTMLResponse:
    return HTMLResponse(
        pages.message_page("Dashboard session expired", "Run 'authsome ui' to reopen the hosted dashboard."),
        status_code=status_code,
    )


def _set_ui_session_cookie(
    response: Response,
    session_id: str,
    ui_sessions: UiSessionStore,
    server_base_url: str,
) -> None:
    response.set_cookie(
        UI_SESSION_COOKIE_NAME,
        ui_sessions.build_cookie_value(session_id),
        httponly=True,
        secure=_ui_cookie_secure(server_base_url),
        samesite="lax",
        path="/",
    )


def _clear_ui_session_cookie(response: Response) -> None:
    response.delete_cookie(UI_SESSION_COOKIE_NAME, path="/")


def _page_context(request: Request, page: str, **kwargs: Any) -> dict[str, Any]:
    return {
        "page": page,
        "version": __version__,
        "ui_identity": getattr(request.state, "ui_identity", None),
        **_ui_policy(),
        **kwargs,
    }


def _format_relative(when: datetime | None) -> str | None:
    """Return a compact "in 47 minutes" / "2 days ago" label."""
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    delta_seconds = int((when - datetime.now(UTC)).total_seconds())
    abs_seconds = abs(delta_seconds)
    direction = "in" if delta_seconds >= 0 else "ago"

    if abs_seconds < 60:
        amount, unit = abs_seconds, "second"
    elif abs_seconds < 3600:
        amount, unit = abs_seconds // 60, "minute"
    elif abs_seconds < 86400:
        amount, unit = abs_seconds // 3600, "hour"
    else:
        amount, unit = abs_seconds // 86400, "day"

    plural = "" if amount == 1 else "s"
    return f"{direction} {amount} {unit}{plural}" if direction == "in" else f"{amount} {unit}{plural} ago"


def _provider_status(provider_name: str, connection_summaries: list[dict[str, Any]]) -> str:
    """Map a connection list to a single status string for the overview cards."""
    if not connection_summaries:
        return "available"
    statuses = {c.get("status") for c in connection_summaries}
    if "error" in statuses or "expired" in statuses:
        return "reauth"
    return "connected"


def _logo_initial(name: str) -> str:
    return (name[:1] or "?").upper()


def _build_provider_view(
    provider: ProviderDefinition,
    source: str,
    connections: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "name": provider.name,
        "display_name": provider.display_name,
        "auth_type": provider.auth_type.value,
        "auth_type_label": "OAuth 2.0" if provider.auth_type == AuthType.OAUTH2 else "API Key",
        "api_url": provider.api_url or (provider.oauth.base_url if provider.oauth else None) or provider.name,
        "description": (provider.metadata or {}).get("description", ""),
        "source": source,
        "logo_initial": _logo_initial(provider.display_name or provider.name),
        "status": _provider_status(provider.name, connections),
        "connections": connections,
        "scope_count": len(connections[0].get("scopes") or []) if connections else 0,
    }


async def _all_provider_views(auth: AuthService) -> list[dict[str, Any]]:
    by_source = await auth.list_providers_by_source()
    connections_by_provider = {group["name"]: group["connections"] for group in await auth.list_connections()}
    views: list[dict[str, Any]] = []
    for source in ("bundled", "custom"):
        for provider in by_source.get(source, []):
            views.append(_build_provider_view(provider, source, connections_by_provider.get(provider.name, [])))
    return views


@router.get("/", response_class=HTMLResponse)
async def overview(request: Request) -> HTMLResponse:
    auth = await _resolve_ui_auth(request)
    if auth is None:
        return _ui_session_expired_response()
    providers = await _all_provider_views(auth)
    connected = [p for p in providers if p["status"] != "available"]
    available_count = len(providers) - len(connected)
    oauth_count = sum(1 for p in connected if p["auth_type"] == AuthType.OAUTH2.value)
    apikey_count = sum(1 for p in connected if p["auth_type"] == AuthType.API_KEY.value)

    # "Last activity" ~ most recent token issue/refresh time across connections.
    last_activity_label: str | None = None
    most_recent: datetime | None = None
    for view in connected:
        for conn in view["connections"]:
            for ts_field in ("expires_at",):
                ts = conn.get(ts_field)
                if not ts:
                    continue
                try:
                    parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except (TypeError, ValueError):
                    continue
                if most_recent is None or parsed > most_recent:
                    most_recent = parsed
    if most_recent is not None:
        last_activity_label = _format_relative(most_recent)

    return templates.TemplateResponse(
        request,
        "overview.html",
        _page_context(
            request,
            "overview",
            stats={
                "connected": len(connected),
                "available": available_count,
                "oauth": oauth_count,
                "api_key": apikey_count,
            },
            last_activity=last_activity_label or "—",
            connected_providers=connected[:6],
        ),
    )


@router.get("/connections", response_class=HTMLResponse)
async def connections(request: Request) -> HTMLResponse:
    auth = await _resolve_ui_auth(request)
    if auth is None:
        return _ui_session_expired_response()
    providers = await _all_provider_views(auth)
    connected_count = sum(1 for p in providers if p["status"] != "available")
    return templates.TemplateResponse(
        request,
        "connections.html",
        _page_context(
            request,
            "connections",
            providers=providers,
            totals={
                "all": len(providers),
                "connected": connected_count,
                "available": len(providers) - connected_count,
            },
        ),
    )


@router.get("/apps/{provider_name}", response_class=HTMLResponse)
async def app_detail(
    provider_name: str,
    request: Request,
    server_base_url: str = Depends(get_server_base_url),
) -> Response:
    auth = await _resolve_ui_auth(request)
    if auth is None:
        return _ui_session_expired_response()
    provider = await auth.get_provider(provider_name)

    connection_record = None
    try:
        connection_record = await auth.get_connection(provider_name)
    except ConnectionNotFoundError:
        pass

    client_record = await auth.get_provider_client(provider_name)
    redirect_uri = build_callback_url(server_base_url)
    api_url = provider.api_url or (provider.oauth.base_url if provider.oauth else None) or provider.name
    policy = _ui_policy()

    if connection_record is None:
        return templates.TemplateResponse(
            request,
            "app_detail_disconnected.html",
            _page_context(
                request,
                "connections",
                provider=provider,
                connection=None,
                logo_initial=_logo_initial(provider.display_name or provider.name),
                api_url=api_url,
                obtained_label=None,
                auth_type_label="OAuth 2.0" if provider.auth_type == AuthType.OAUTH2 else "API Key",
                client_id=client_record.client_id if client_record and policy["show_provider_client_details"] else None,
                has_client_secret=bool(
                    client_record and client_record.client_secret and policy["show_provider_client_details"]
                ),
                redirect_uri=redirect_uri,
                auth_url=provider.oauth.authorization_url if provider.oauth else None,
                token_url=provider.oauth.token_url if provider.oauth else None,
                base_url=(provider.oauth.base_url if provider.oauth else None) or provider.api_url,
            ),
        )

    common = _page_context(
        request,
        "connections",
        provider=provider,
        connection=connection_record,
        logo_initial=_logo_initial(provider.display_name or provider.name),
        api_url=api_url,
        expires_label=_format_relative(connection_record.expires_at),
        obtained_label=_format_relative(connection_record.obtained_at),
        scopes=connection_record.scopes or [],
    )

    if provider.auth_type == AuthType.OAUTH2:
        return templates.TemplateResponse(
            request,
            "app_detail_oauth.html",
            {
                **common,
                "client_id": (
                    client_record.client_id if client_record and policy["show_provider_client_details"] else None
                ),
                "has_client_secret": bool(
                    client_record and client_record.client_secret and policy["show_provider_client_details"]
                ),
                "redirect_uri": redirect_uri,
                "auth_url": provider.oauth.authorization_url if provider.oauth else "",
                "token_url": provider.oauth.token_url if provider.oauth else "",
                "access_token": connection_record.access_token,
                "refresh_token": connection_record.refresh_token,
            },
        )

    return templates.TemplateResponse(
        request,
        "app_detail_apikey.html",
        {
            **common,
            "api_key": connection_record.api_key,
            "base_url": connection_record.base_url
            or (provider.oauth.base_url if provider.oauth else None)
            or provider.api_url,
        },
    )


@router.post("/apps/{provider_name}/{connection_name}/disconnect")
async def disconnect_app(
    provider_name: str,
    connection_name: str,
    request: Request,
) -> Response:
    """Disconnect a provider connection from the dashboard."""
    auth = await _resolve_ui_auth(request)
    if auth is None:
        return _redirect(request, "/ui/")
    await auth.logout(provider_name, connection_name)
    return _redirect(request, "/ui/connections")


@router.post("/apps/{provider_name}/connect")
async def connect_app(
    provider_name: str,
    request: Request,
    background_tasks: BackgroundTasks,
    sessions: AuthSessionStore = Depends(get_auth_sessions),
    server_base_url: str = Depends(get_server_base_url),
) -> Response:
    """Start a provider connection from the dashboard."""
    auth = await _resolve_ui_auth(request)
    if auth is None:
        return _redirect(request, "/ui/")
    form = await request.form()
    connection_name = str(form.get("connection", "default") or "default")
    force = str(form.get("force", "false")).lower() in {"1", "true", "on", "yes"}

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
    session.payload["return_url"] = f"{server_base_url.rstrip('/')}/ui/apps/{provider_name}"
    if _is_hosted_ui():
        session.payload["ui_session_required"] = True

    if not force:
        try:
            existing = await auth.get_connection(provider_name, connection_name)
            if auth._connection_is_valid(existing):
                session.status_message = "Already connected"
                await sessions.save(session)
                return _redirect(request, f"/ui/apps/{provider_name}")
        except Exception:
            pass

    fields = await auth.get_required_inputs(session)
    if fields:
        session.payload["input_fields"] = [field.model_dump(mode="json", exclude_none=True) for field in fields]
        await sessions.save(session)
        return _redirect(request, build_auth_input_url(server_base_url, session.session_id))

    await auth.begin_login_flow(session=session, force=force)
    if flow == FlowType.DEVICE_CODE:
        _update_device_code_expiry(sessions, session)
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
    return _redirect(request, f"/ui/apps/{provider_name}")


@router.post("/session", response_model=UiBootstrapResponse)
async def start_ui_session(
    auth: AuthService = Depends(get_protected_auth_service),
    ui_sessions: UiSessionStore = Depends(get_ui_sessions),
    server_base_url: str = Depends(get_server_base_url),
) -> UiBootstrapResponse:
    """Return a browser URL for opening the dashboard as the authenticated identity."""
    if not _is_hosted_ui():
        return UiBootstrapResponse(url=f"{server_base_url.rstrip('/')}/ui/")

    bootstrap = ui_sessions.create_bootstrap(identity=auth.identity, principal_id=auth.principal_id or "")
    return UiBootstrapResponse(url=f"{server_base_url.rstrip('/')}/ui/bootstrap/{bootstrap.token}")


@router.get("/bootstrap/{token}", include_in_schema=False)
async def consume_bootstrap(
    token: str,
    ui_sessions: UiSessionStore = Depends(get_ui_sessions),
    server_base_url: str = Depends(get_server_base_url),
) -> Response:
    """Consume a one-time UI bootstrap token and set the browser session cookie."""
    if not _is_hosted_ui():
        return RedirectResponse(url="/ui/", status_code=303)

    try:
        session = ui_sessions.consume_bootstrap(token)
    except KeyError:
        return _ui_session_expired_response(status_code=404)

    response = RedirectResponse(url="/ui/", status_code=303)
    _set_ui_session_cookie(response, session.session_id, ui_sessions, server_base_url)
    return response


@router.post("/logout")
async def logout_ui_session(
    request: Request,
    ui_sessions: UiSessionStore = Depends(get_ui_sessions),
) -> Response:
    """Clear the hosted dashboard browser session."""
    response = _redirect(request, "/ui/")
    cookie_value = request.cookies.get(UI_SESSION_COOKIE_NAME)
    if cookie_value:
        try:
            session = ui_sessions.get_session(cookie_value)
        except KeyError:
            session = None
        if session is not None:
            ui_sessions.delete_session(session.session_id)
    _clear_ui_session_cookie(response)
    return response


@router.get("/claim/{token}", include_in_schema=False, response_class=HTMLResponse)
async def claim_identity_page(token: str, ui_sessions: UiSessionStore = Depends(get_ui_sessions)) -> HTMLResponse:
    try:
        bootstrap = ui_sessions._claim_bootstraps[token]
    except KeyError:
        return _ui_session_expired_response(status_code=404)
    claim_form = (
        f'<form method="post" action="/ui/claim/{token}">'
        '<label for="email">Email</label>'
        '<input id="email" type="email" name="email" required '
        'style="display:block;margin:12px 0;padding:8px;width:100%;max-width:360px;">'
        '<button type="submit">Claim identity</button>'
        "</form></main>"
    )
    return HTMLResponse(
        pages.message_page(
            "Claim Identity",
            (
                f"Complete the claim for identity '{bootstrap.identity}' by submitting your email "
                "to the claim form at this URL."
            ),
        ).replace("</main>", claim_form)
    )


@router.post("/claim/{token}", include_in_schema=False)
async def claim_identity_submit(
    token: str,
    request: Request,
    ui_sessions: UiSessionStore = Depends(get_ui_sessions),
    server_base_url: str = Depends(get_server_base_url),
) -> Response:
    try:
        bootstrap = ui_sessions.consume_claim_bootstrap(token)
    except KeyError:
        return _ui_session_expired_response(status_code=404)

    form = await request.form()
    email = str(form.get("email", "")).strip()
    if not email:
        return HTMLResponse(pages.message_page("Claim failed", "Email is required."), status_code=400)

    resolved = await request.app.state.ownership_resolver.ensure_claimed_identity(
        identity=bootstrap.identity, email=email
    )
    session = ui_sessions.create_session(
        identity=bootstrap.identity,
        principal_id=resolved.principal_id,
    )
    response = RedirectResponse(url="/ui/", status_code=303)
    _set_ui_session_cookie(response, session.session_id, ui_sessions, server_base_url)
    return response
