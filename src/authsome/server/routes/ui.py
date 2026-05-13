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
from authsome.server.routes._deps import get_auth_service, get_auth_sessions, get_server_base_url
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
        "host_url": provider.host_url or (provider.oauth.base_url if provider.oauth else None) or provider.name,
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
async def overview(request: Request, auth: AuthService = Depends(get_auth_service)) -> HTMLResponse:
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
        {
            "page": "overview",
            "version": __version__,
            "stats": {
                "connected": len(connected),
                "available": available_count,
                "oauth": oauth_count,
                "api_key": apikey_count,
            },
            "last_activity": last_activity_label or "—",
            "connected_providers": connected[:6],
        },
    )


@router.get("/connections", response_class=HTMLResponse)
async def connections(request: Request, auth: AuthService = Depends(get_auth_service)) -> HTMLResponse:
    providers = await _all_provider_views(auth)
    connected_count = sum(1 for p in providers if p["status"] != "available")
    return templates.TemplateResponse(
        request,
        "connections.html",
        {
            "page": "connections",
            "version": __version__,
            "providers": providers,
            "totals": {
                "all": len(providers),
                "connected": connected_count,
                "available": len(providers) - connected_count,
            },
        },
    )


@router.get("/apps/{provider_name}", response_class=HTMLResponse)
async def app_detail(
    provider_name: str,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
    server_base_url: str = Depends(get_server_base_url),
) -> Response:
    provider = await auth.get_provider(provider_name)

    connection_record = None
    try:
        connection_record = await auth.get_connection(provider_name)
    except ConnectionNotFoundError:
        pass

    client_record = await auth.get_provider_client(provider_name)
    redirect_uri = build_callback_url(server_base_url)
    host_url = provider.host_url or (provider.oauth.base_url if provider.oauth else None) or provider.name

    if connection_record is None:
        return templates.TemplateResponse(
            request,
            "app_detail_disconnected.html",
            {
                "page": "connections",
                "version": __version__,
                "provider": provider,
                "connection": None,
                "logo_initial": _logo_initial(provider.display_name or provider.name),
                "host_url": host_url,
                "obtained_label": None,
                "auth_type_label": "OAuth 2.0" if provider.auth_type == AuthType.OAUTH2 else "API Key",
                "client_id": (client_record.client_id if client_record else None),
                "has_client_secret": bool(client_record and client_record.client_secret),
                "redirect_uri": redirect_uri,
                "auth_url": provider.oauth.authorization_url if provider.oauth else None,
                "token_url": provider.oauth.token_url if provider.oauth else None,
                "base_url": (provider.oauth.base_url if provider.oauth else None) or provider.host_url,
            },
        )

    common = {
        "page": "connections",
        "version": __version__,
        "provider": provider,
        "connection": connection_record,
        "logo_initial": _logo_initial(provider.display_name or provider.name),
        "host_url": host_url,
        "expires_label": _format_relative(connection_record.expires_at),
        "obtained_label": _format_relative(connection_record.obtained_at),
        "scopes": connection_record.scopes or [],
    }

    if provider.auth_type == AuthType.OAUTH2:
        return templates.TemplateResponse(
            request,
            "app_detail_oauth.html",
            {
                **common,
                "client_id": (client_record.client_id if client_record else None),
                "has_client_secret": bool(client_record and client_record.client_secret),
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
            or provider.host_url,
        },
    )


@router.post("/apps/{provider_name}/{connection_name}/disconnect")
async def disconnect_app(
    provider_name: str,
    connection_name: str,
    request: Request,
    auth: AuthService = Depends(get_auth_service),
) -> Response:
    """Disconnect a provider connection from the dashboard."""
    await auth.logout(provider_name, connection_name)
    return _redirect(request, "/ui/connections")


@router.post("/apps/{provider_name}/connect")
async def connect_app(
    provider_name: str,
    request: Request,
    background_tasks: BackgroundTasks,
    auth: AuthService = Depends(get_auth_service),
    sessions: AuthSessionStore = Depends(get_auth_sessions),
    server_base_url: str = Depends(get_server_base_url),
) -> Response:
    """Start a provider connection from the dashboard."""
    form = await request.form()
    connection_name = str(form.get("connection", "default") or "default")
    force = str(form.get("force", "false")).lower() in {"1", "true", "on", "yes"}

    definition = await auth.get_provider(provider_name)
    flow = definition.flow
    session = sessions.create(
        provider=provider_name,
        identity=auth.identity,
        connection_name=connection_name,
        flow_type=flow.value,
    )
    session.payload["force"] = force
    session.payload["callback_url_override"] = build_callback_url(server_base_url)
    session.payload["return_url"] = f"{server_base_url.rstrip('/')}/ui/apps/{provider_name}"

    if not force:
        try:
            existing = await auth.get_connection(provider_name, connection_name)
            if auth._connection_is_valid(existing):
                session.status_message = "Already connected"
                return _redirect(request, f"/ui/apps/{provider_name}")
        except Exception:
            pass

    fields = await auth.get_required_inputs(session)
    if fields:
        session.payload["input_fields"] = [field.model_dump(mode="json", exclude_none=True) for field in fields]
        return _redirect(request, build_auth_input_url(server_base_url, session.session_id))

    await auth.begin_login_flow(session=session, force=force)
    if flow == FlowType.DEVICE_CODE:
        _update_device_code_expiry(sessions, session)
        background_tasks.add_task(auth.background_resume, session)
        if session.payload.get("user_code") and session.payload.get("verification_uri"):
            return _redirect(request, build_device_url(server_base_url, session.session_id))

    sessions.index_oauth_state(session)
    auth_url = session.payload.get("auth_url")
    if auth_url:
        return _redirect(request, str(auth_url))
    return _redirect(request, f"/ui/apps/{provider_name}")
