"""HTML routes that render the Authsome local dashboard.

The UI is intentionally server-rendered against the same FastAPI app that
serves the JSON daemon API. This keeps it a single process on port 7998
and avoids a separate static server.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from importlib.resources import files
from typing import Any
from urllib.parse import urlencode

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from authsome import __version__
from authsome.auth.models.connection import ConnectionRecord, ProviderClientRecord
from authsome.auth.models.enums import AuthType, FlowType
from authsome.auth.models.provider import ProviderDefinition
from authsome.auth.sessions import AuthSession, AuthSessionStore
from authsome.server.credential_service import AuthService
from authsome.server.dependencies import (
    create_principal_vault_binding_registry,
    create_vault_registry,
    get_deployment_mode,
)
from authsome.server.routes._deps import (
    UI_SESSION_COOKIE_NAME,
    get_auth_service,
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


class UiAuthRequiredError(Exception):
    """Raised when a UI route needs to return an auth-related response."""

    def __init__(self, response: Response) -> None:
        self.response = response


async def _resolve_ui_auth(request: Request, *, next_url: str | None = None) -> AuthService:
    identity = await resolve_ui_request_identity(request)
    auth = await get_auth_service(
        request,
        identity=identity,
        principal_id=getattr(request.state, "ui_principal_id", None),
    )
    if auth is not None:
        return auth

    if _is_hosted_ui():
        target = _hosted_auth_next_url(next_url or request.query_params.get("next") or request.url.path)
        if request.method == "GET" and request.url.path == "/ui/":
            raise UiAuthRequiredError(_hosted_auth_page_response(request.app.state.ui_sessions, next_url=target))
        raise UiAuthRequiredError(RedirectResponse(url=_hosted_auth_entry_url(target), status_code=303))

    raise UiAuthRequiredError(_ui_session_expired_response())


def require_ui_auth(next_url: str | None = None) -> Callable[[Request], Awaitable[AuthService]]:
    async def dependency(request: Request) -> AuthService:
        return await _resolve_ui_auth(request, next_url=next_url)

    return dependency


def _ui_session_expired_response(status_code: int = 401) -> HTMLResponse:
    return HTMLResponse(
        pages.message_page("Dashboard session expired", "Run 'authsome ui' to reopen the hosted dashboard."),
        status_code=status_code,
    )


def _hosted_auth_entry_url(next_url: str = "/ui/") -> str:
    return f"/ui/?{urlencode({'next': _hosted_auth_next_url(next_url)})}"


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


def _hosted_auth_next_url(value: Any) -> str:
    next_url = str(value or "/ui/").strip() or "/ui/"
    if not next_url.startswith("/ui/"):
        return "/ui/"
    return next_url


def _pending_claim_for_next_url(ui_sessions: UiSessionStore, next_url: str):
    if not next_url.startswith("/ui/claim/"):
        raise KeyError("Hosted auth request is not tied to a pending claim")
    token = next_url.rstrip("/").rsplit("/", 1)[-1]
    return ui_sessions.get_pending_claim(token)


def _hosted_auth_page_response(
    ui_sessions: UiSessionStore,
    *,
    next_url: str,
    error: str | None = None,
    active_tab: str = "login",
) -> HTMLResponse:
    next_url = _hosted_auth_next_url(next_url)
    if next_url.startswith("/ui/claim/"):
        pending = _pending_claim_for_next_url(ui_sessions, next_url)
        page = pages.hosted_claim_auth_page(
            token=pending.token,
            identity=pending.identity,
            error=error,
            active_tab=active_tab,
        )
    else:
        page = pages.hosted_auth_page(next_url=next_url, error=error, active_tab=active_tab)
    return HTMLResponse(page, status_code=400 if error else 200)


def _page_context(request: Request, page: str, **kwargs: Any) -> dict[str, Any]:
    return {
        "page": page,
        "version": __version__,
        "ui_identity": getattr(request.state, "ui_identity", None),
        "ui_email": getattr(request.state, "ui_email", None),
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


async def _provider_connection_groups(
    request: Request,
    *,
    identity: str,
    principal_id: str | None,
    provider_name: str,
) -> list[dict[str, Any]]:
    if not principal_id:
        return []

    bindings = create_principal_vault_binding_registry(request.app.state.store.home)
    vaults = create_vault_registry(request.app.state.store.home)
    groups: list[dict[str, Any]] = []

    for binding in await bindings.list_for_principal(principal_id):
        scoped_auth = AuthService(
            vault=request.app.state.vault,
            identity=identity,
            principal_id=principal_id,
            vault_id=binding.vault_id,
            deployment_mode=get_deployment_mode(),
        )
        provider_connections = next(
            (group["connections"] for group in await scoped_auth.list_connections() if group["name"] == provider_name),
            [],
        )
        if not provider_connections:
            continue

        vault_record = await vaults.get(binding.vault_id)
        group_items: list[dict[str, Any]] = []
        for connection in provider_connections:
            record = await scoped_auth.get_connection(provider_name, connection["connection_name"])
            group_items.append(
                {
                    "connection_name": connection["connection_name"],
                    "identity": record.identity,
                    "status": connection["status"],
                    "href": f"/ui/apps/{provider_name}/connections/{connection['connection_name']}",
                }
            )

        groups.append(
            {
                "vault_label": (vault_record.handle if vault_record else "default").replace("-", " ").title(),
                "connections": group_items,
            }
        )

    return groups


def _provider_page_context(
    request: Request,
    provider: ProviderDefinition,
    api_url: str,
    *,
    grouped_connections: list[dict[str, Any]],
    provider_client: ProviderClientRecord | None,
    redirect_uri: str,
    auth_url: str | None,
    token_url: str | None,
) -> dict[str, Any]:
    policy = _ui_policy()
    return _page_context(
        request,
        "applications",
        provider=provider,
        connection=None,
        grouped_connections=grouped_connections,
        logo_initial=_logo_initial(provider.display_name or provider.name),
        api_url=api_url,
        auth_type_label="OAuth 2.0" if provider.auth_type == AuthType.OAUTH2 else "API Key",
        client_id=provider_client.client_id if provider_client and policy["show_provider_client_details"] else None,
        has_client_secret=bool(
            provider_client and provider_client.client_secret and policy["show_provider_client_details"]
        ),
        redirect_uri=redirect_uri,
        auth_url=auth_url,
        token_url=token_url,
        requires_named_login=any(
            connection["connection_name"] == "default"
            for group in grouped_connections
            for connection in group["connections"]
        ),
    )


def _connection_detail_context(
    request: Request,
    provider: ProviderDefinition,
    connection_record: ConnectionRecord,
    api_url: str,
) -> dict[str, Any]:
    return _page_context(
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


async def _all_provider_views(auth: AuthService) -> list[dict[str, Any]]:
    by_source = await auth.list_providers_by_source()
    connections_by_provider = {group["name"]: group["connections"] for group in await auth.list_connections()}
    views: list[dict[str, Any]] = []
    for source in ("bundled", "custom"):
        for provider in by_source.get(source, []):
            views.append(_build_provider_view(provider, source, connections_by_provider.get(provider.name, [])))
    return views


def _build_connection_rows(providers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for provider in providers:
        for connection in provider["connections"]:
            rows.append(
                {
                    "provider_name": provider["name"],
                    "provider_display_name": provider["display_name"],
                    "connection_name": connection["connection_name"],
                    "status": connection["status"],
                    "auth_type_label": provider["auth_type_label"],
                    "href": f"/ui/apps/{provider['name']}/connections/{connection['connection_name']}",
                }
            )
    return sorted(rows, key=lambda row: (row["provider_display_name"].lower(), row["connection_name"].lower()))


@router.get("/", response_class=HTMLResponse)
async def overview(
    request: Request,
    auth: AuthService = Depends(require_ui_auth()),
) -> HTMLResponse:
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


@router.get("/applications", response_class=HTMLResponse)
async def applications(
    request: Request,
    auth: AuthService = Depends(require_ui_auth("/ui/applications")),
) -> Response:
    providers = [
        {
            **provider,
            "requires_named_login": any(
                connection["connection_name"] == "default" for connection in provider["connections"]
            ),
        }
        for provider in await _all_provider_views(auth)
    ]
    return templates.TemplateResponse(
        request,
        "applications.html",
        _page_context(request, "applications", providers=providers),
    )


@router.get("/connections", response_class=HTMLResponse)
async def connections(
    request: Request,
    auth: AuthService = Depends(require_ui_auth("/ui/connections")),
) -> Response:
    providers = await _all_provider_views(auth)
    rows = _build_connection_rows(providers)
    return templates.TemplateResponse(
        request,
        "connections.html",
        _page_context(
            request,
            "connections",
            connection_rows=rows,
            total_connections=len(rows),
        ),
    )


@router.get("/identity", response_class=HTMLResponse)
async def identity_page(
    request: Request,
    auth: AuthService = Depends(require_ui_auth("/ui/identity")),
) -> Response:
    if _is_hosted_ui():
        claims = await request.app.state.identity_claim_registry.list_for_principal(request.state.ui_principal_id)
        identities = [{"handle": claim.identity_handle, "is_active": False} for claim in claims]
    else:
        identities = [{"handle": auth.identity, "is_active": True}]
    return templates.TemplateResponse(
        request,
        "identity.html",
        _page_context(
            request,
            "identity",
            identities=identities,
            principal_id=auth.principal_id,
        ),
    )


@router.get("/apps/{provider_name}", response_class=HTMLResponse)
async def app_detail(
    provider_name: str,
    request: Request,
    auth: AuthService = Depends(require_ui_auth()),
    server_base_url: str = Depends(get_server_base_url),
) -> Response:
    provider = await auth.get_provider(provider_name)
    redirect_uri = build_callback_url(server_base_url)
    api_url = provider.api_url or (provider.oauth.base_url if provider.oauth else None) or provider.name
    if _is_hosted_ui():
        return templates.TemplateResponse(
            request,
            "app_detail_managed.html",
            _page_context(
                request,
                "applications",
                provider=provider,
                logo_initial=_logo_initial(provider.display_name or provider.name),
            ),
        )

    client_record = await auth.get_provider_client(provider_name)
    grouped_connections = await _provider_connection_groups(
        request,
        identity=auth.require_identity(),
        principal_id=auth.principal_id,
        provider_name=provider_name,
    )
    return templates.TemplateResponse(
        request,
        "app_provider.html",
        _provider_page_context(
            request,
            provider,
            api_url,
            grouped_connections=grouped_connections,
            provider_client=client_record,
            redirect_uri=redirect_uri,
            auth_url=provider.oauth.authorization_url if provider.oauth else None,
            token_url=provider.oauth.token_url if provider.oauth else None,
        ),
    )


@router.get("/apps/{provider_name}/connections/{connection_name}", response_class=HTMLResponse)
async def connection_detail(
    provider_name: str,
    connection_name: str,
    request: Request,
    auth: AuthService = Depends(require_ui_auth()),
) -> Response:
    provider = await auth.get_provider(provider_name)
    connection_record = await auth.get_connection(provider_name, connection_name)
    api_url = provider.api_url or (provider.oauth.base_url if provider.oauth else None) or provider.name
    common = _connection_detail_context(request, provider, connection_record, api_url)

    if provider.auth_type == AuthType.OAUTH2:
        return templates.TemplateResponse(
            request,
            "app_detail_oauth.html",
            {
                **common,
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
    auth: AuthService = Depends(require_ui_auth("/ui/connections")),
) -> Response:
    """Disconnect a provider connection from the dashboard."""
    await auth.logout(provider_name, connection_name)
    return _redirect(request, "/ui/connections")


@router.post("/apps/{provider_name}/connect")
async def connect_app(
    provider_name: str,
    request: Request,
    background_tasks: BackgroundTasks,
    auth: AuthService = Depends(require_ui_auth()),
    sessions: AuthSessionStore = Depends(get_auth_sessions),
    server_base_url: str = Depends(get_server_base_url),
) -> Response:
    """Start a provider connection from the dashboard."""
    form = await request.form()
    connection_name = str(form.get("connection") or form.get("connection_name") or "default")
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


@router.post("/apps/{provider_name}/configure")
async def configure_provider(
    provider_name: str,
    request: Request,
    auth: AuthService = Depends(require_ui_auth()),
    sessions: AuthSessionStore = Depends(get_auth_sessions),
    server_base_url: str = Depends(get_server_base_url),
) -> Response:
    """Open the provider configuration flow for deployment-scoped credentials."""
    provider = await auth.get_provider(provider_name)
    if provider.auth_type != AuthType.OAUTH2 or _is_hosted_ui():
        return _redirect(request, f"/ui/apps/{provider_name}")

    session = await sessions.create(
        provider=provider_name,
        identity=auth.identity,
        principal_id=auth.principal_id,
        connection_name="default",
        flow_type=provider.flow.value,
    )
    session.payload["provider_config_only"] = True
    session.payload["existing_provider_client"] = (await auth.get_provider_client(provider_name)) is not None
    session.payload["callback_url_override"] = build_callback_url(server_base_url)
    session.payload["return_url"] = f"{server_base_url.rstrip('/')}/ui/apps/{provider_name}"
    session.payload["input_fields"] = [
        field.model_dump(mode="json", exclude_none=True) for field in await auth.get_required_inputs(session)
    ]
    await sessions.save(session)
    return _redirect(request, build_auth_input_url(server_base_url, session.session_id))


@router.post("/session", response_model=UiBootstrapResponse)
async def start_ui_session(
    auth: AuthService = Depends(get_protected_auth_service),
    server_base_url: str = Depends(get_server_base_url),
) -> UiBootstrapResponse:
    """Return a browser URL for opening the dashboard."""
    _ = auth
    return UiBootstrapResponse(url=f"{server_base_url.rstrip('/')}/ui/")


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
            ui_sessions.delete_browser_session(cookie_value)
        except KeyError:
            pass
    _clear_ui_session_cookie(response)
    return response


@router.get("/claim/{token}", include_in_schema=False, response_class=HTMLResponse)
async def claim_identity_page(
    token: str,
    request: Request,
    ui_sessions: UiSessionStore = Depends(get_ui_sessions),
) -> HTMLResponse:
    try:
        pending = ui_sessions.get_pending_claim(token)
    except KeyError:
        return _ui_session_expired_response(status_code=404)

    await resolve_ui_request_identity(request)
    if _is_hosted_ui() and getattr(request.state, "ui_principal_id", None) is None:
        return HTMLResponse(pages.hosted_claim_auth_page(token=token, identity=pending.identity))

    email = getattr(request.state, "ui_email", None) or "this account"
    return HTMLResponse(pages.hosted_claim_confirm_page(token=token, identity=pending.identity, email=email))


@router.post("/auth/register", include_in_schema=False)
async def register_hosted_account(
    request: Request,
    ui_sessions: UiSessionStore = Depends(get_ui_sessions),
    server_base_url: str = Depends(get_server_base_url),
) -> Response:
    form = await request.form()
    email = str(form.get("email", "")).strip()
    password = str(form.get("password", ""))
    next_url = _hosted_auth_next_url(form.get("next"))

    try:
        session = await request.app.state.hosted_account_service.register_and_login(email=email, password=password)
    except ValueError as exc:
        try:
            return _hosted_auth_page_response(ui_sessions, next_url=next_url, error=str(exc), active_tab="register")
        except KeyError:
            return _ui_session_expired_response(status_code=404)

    response = RedirectResponse(url=next_url, status_code=303)
    _set_ui_session_cookie(response, session.token, ui_sessions, server_base_url)
    return response


@router.post("/auth/login", include_in_schema=False)
async def login_hosted_account(
    request: Request,
    ui_sessions: UiSessionStore = Depends(get_ui_sessions),
    server_base_url: str = Depends(get_server_base_url),
) -> Response:
    form = await request.form()
    email = str(form.get("email", "")).strip()
    password = str(form.get("password", ""))
    next_url = _hosted_auth_next_url(form.get("next"))

    try:
        session = await request.app.state.hosted_account_service.login(email=email, password=password)
    except ValueError as exc:
        try:
            return _hosted_auth_page_response(ui_sessions, next_url=next_url, error=str(exc), active_tab="login")
        except KeyError:
            return _ui_session_expired_response(status_code=404)

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
        return _ui_session_expired_response(status_code=404)

    await resolve_ui_request_identity(request)
    principal_id = getattr(request.state, "ui_principal_id", None)
    if not principal_id:
        return _ui_session_expired_response(status_code=401)

    pending = ui_sessions.consume_pending_claim(token)
    await request.app.state.ownership_resolver.claim_identity_for_principal(
        identity=pending.identity,
        principal_id=principal_id,
    )
    request.app.state.ownership_cache.pop(pending.identity, None)
    return RedirectResponse(url="/ui/", status_code=303)
