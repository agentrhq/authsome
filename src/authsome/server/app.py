"""FastAPI app factory for the Authsome daemon."""

from contextlib import asynccontextmanager, suppress
from importlib.resources import files

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from authsome.errors import AuthsomeError
from authsome.server.analytics import init_posthog, shutdown_posthog
from authsome.server.dependencies import (
    create_account_auth_service,
    create_identity_bootstrap_service,
    create_ownership_resolver,
    create_runtime_state,
    create_store,
    create_vault,
    get_server_base_url,
    load_server_config,
)
from authsome.server.provider_repository import ProviderRepository
from authsome.server.routes.audit import router as audit_router
from authsome.server.routes.auth import browser_router as auth_browser_router
from authsome.server.routes.auth import router as auth_router
from authsome.server.routes.connections import router as connections_router
from authsome.server.routes.health import HealthResponse, build_health_response
from authsome.server.routes.health import router as health_router
from authsome.server.routes.identities import router as identities_router
from authsome.server.routes.principals import router as principals_router
from authsome.server.routes.providers import router as providers_router
from authsome.server.routes.proxy import router as proxy_router
from authsome.server.routes.ui import UiAuthRequiredError
from authsome.server.routes.ui import router as ui_router
from authsome.server.secrets import load_ui_session_signing_secret
from authsome.server.store.repositories import IdentityRegistrationError
from authsome.server.ui_sessions import UiSessionStore


async def _cleanup_startup_resources(store, audit_log, runtime_state) -> None:
    with suppress(Exception):
        if audit_log is not None:
            await audit_log.async_shutdown()
    with suppress(Exception):
        if store is not None:
            await store.close()
    with suppress(Exception):
        if runtime_state is not None:
            await runtime_state.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage daemon lifecycle."""
    store = audit_log = runtime_state = None
    try:
        store = await create_store()
        server_config = await load_server_config(store)
        audit_log = store.audit_events.configure_exporter()
        vault = await create_vault(store.home)
        runtime_state = await create_runtime_state()
        auth_sessions = runtime_state.auth_sessions
        proof_replay_cache = runtime_state.replay_cache
        ui_sessions = UiSessionStore(
            load_ui_session_signing_secret(store.home),
            pending_claims=runtime_state.pending_claims,
        )
        provider_repository = ProviderRepository(store.provider_definitions)
        account_auth_service = create_account_auth_service(store, ui_sessions)
        server_base_url = get_server_base_url()
        init_posthog()
        identity_bootstrap = create_identity_bootstrap_service(
            store.identity_registry,
            ui_sessions,
            store=store,
            server_base_url=server_base_url,
        )
        ownership_resolver = create_ownership_resolver(store)
        ownership_cache = {}
    except Exception:
        await _cleanup_startup_resources(store, audit_log, runtime_state)
        raise

    app.state.store = store
    app.state.server_config = server_config
    app.state.audit_log = audit_log
    app.state.vault = vault
    app.state.runtime_state = runtime_state
    app.state.auth_sessions = auth_sessions
    app.state.proof_replay_cache = proof_replay_cache
    app.state.ui_sessions = ui_sessions
    app.state.provider_repository = provider_repository
    app.state.account_auth_service = account_auth_service
    app.state.server_base_url = server_base_url
    app.state.identity_bootstrap = identity_bootstrap
    app.state.ownership_resolver = ownership_resolver
    app.state.ownership_cache = ownership_cache
    yield
    try:
        shutdown_posthog()
        if audit_log is not None:
            await audit_log.async_shutdown()
        if store is not None:
            await store.close()
    finally:
        if runtime_state is not None:
            await runtime_state.close()


def create_app() -> FastAPI:
    """Create the local daemon FastAPI app."""
    app = FastAPI(title="Authsome Daemon", version="0.1", lifespan=lifespan)

    @app.exception_handler(AuthsomeError)
    def authsome_error_handler(request: Request, exc: AuthsomeError) -> JSONResponse:
        status_code = status.HTTP_400_BAD_REQUEST
        exc_name = exc.__class__.__name__
        if exc_name in ("ConnectionNotFoundError", "ProviderNotFoundError", "IdentityNotFoundError"):
            status_code = status.HTTP_404_NOT_FOUND
        elif exc_name == "CredentialMissingError":
            status_code = status.HTTP_401_UNAUTHORIZED

        return JSONResponse(
            status_code=status_code,
            content={
                "error": exc_name,
                "message": Exception.__str__(exc),
                "provider": exc.provider,
                "operation": exc.operation,
            },
        )

    @app.exception_handler(IdentityRegistrationError)
    def identity_registration_error_handler(request: Request, exc: IdentityRegistrationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT, content={"error": "IdentityRegistrationError", "message": str(exc)}
        )

    @app.exception_handler(UiAuthRequiredError)
    def ui_auth_required_handler(request: Request, exc: UiAuthRequiredError):
        return exc.response

    @app.get("/claim/{token}", include_in_schema=False)
    def claim_page_redirect(token: str) -> RedirectResponse:
        return RedirectResponse(url=f"/claim?token={token}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    @app.get("/health", response_model=HealthResponse)
    def root_health(request: Request) -> HealthResponse:
        return build_health_response(request)

    app.include_router(auth_browser_router)
    app.include_router(health_router, prefix="/api")
    app.include_router(identities_router, prefix="/api")
    app.include_router(principals_router, prefix="/api")
    app.include_router(audit_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(connections_router, prefix="/api")
    app.include_router(providers_router, prefix="/api")
    app.include_router(proxy_router, prefix="/api")
    app.include_router(ui_router, prefix="/api")

    ui_dir = files("authsome.ui").joinpath("web")
    app.mount("/", StaticFiles(directory=str(ui_dir), html=True, check_dir=False), name="ui")

    return app
