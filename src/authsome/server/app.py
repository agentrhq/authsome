"""FastAPI app factory for the Authsome daemon."""

from __future__ import annotations

from contextlib import asynccontextmanager
from importlib.resources import files

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from authsome.auth.sessions import AuthSessionStore
from authsome.errors import AuthsomeError
from authsome.identity.proof import ReplayCache
from authsome.server.analytics import init_posthog, shutdown_posthog
from authsome.server.dependencies import (
    create_account_auth_service,
    create_identity_bootstrap_service,
    create_ownership_resolver,
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
from authsome.server.routes.health import router as health_router
from authsome.server.routes.identities import router as identities_router
from authsome.server.routes.providers import router as providers_router
from authsome.server.routes.proxy import router as proxy_router
from authsome.server.routes.ui import UiAuthRequiredError
from authsome.server.routes.ui import router as ui_router
from authsome.server.secrets import load_ui_session_signing_secret
from authsome.server.store.repositories import IdentityRegistrationError
from authsome.server.ui_sessions import UiSessionStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage daemon lifecycle."""
    app.state.store = await create_store()
    app.state.server_config = await load_server_config(app.state.store)
    app.state.audit_log = app.state.store.audit_events.configure_exporter()
    app.state.vault = await create_vault(app.state.store.home)
    app.state.auth_sessions = AuthSessionStore()
    app.state.ui_sessions = UiSessionStore(load_ui_session_signing_secret(app.state.store.home))
    app.state.proof_replay_cache = ReplayCache()
    app.state.provider_repository = ProviderRepository(app.state.store.provider_definitions)
    app.state.account_auth_service = create_account_auth_service(app.state.store, app.state.ui_sessions)
    app.state.server_base_url = get_server_base_url()
    init_posthog()
    app.state.identity_bootstrap = create_identity_bootstrap_service(
        app.state.store.identity_registry,
        app.state.ui_sessions,
        store=app.state.store,
        server_base_url=app.state.server_base_url,
    )
    app.state.ownership_resolver = create_ownership_resolver(app.state.store)
    app.state.ownership_cache = {}
    yield
    shutdown_posthog()
    app.state.audit_log.shutdown()
    await app.state.store.close()


def create_app() -> FastAPI:
    """Create the local daemon FastAPI app."""
    app = FastAPI(title="Authsome Daemon", version="0.1", lifespan=lifespan)

    @app.exception_handler(AuthsomeError)
    def authsome_error_handler(request: Request, exc: AuthsomeError) -> JSONResponse:
        status_code = 400
        exc_name = exc.__class__.__name__
        if exc_name in ("ConnectionNotFoundError", "ProviderNotFoundError", "IdentityNotFoundError"):
            status_code = 404
        elif exc_name == "CredentialMissingError":
            status_code = 401

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
        return JSONResponse(status_code=409, content={"error": "IdentityRegistrationError", "message": str(exc)})

    @app.exception_handler(UiAuthRequiredError)
    def ui_auth_required_handler(request: Request, exc: UiAuthRequiredError):
        return exc.response

    @app.get("/claim/{token}", include_in_schema=False)
    def claim_page_redirect(token: str) -> RedirectResponse:
        return RedirectResponse(url=f"/claim?token={token}", status_code=307)

    app.include_router(auth_browser_router)
    app.include_router(health_router, prefix="/api")
    app.include_router(identities_router, prefix="/api")
    app.include_router(audit_router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(connections_router, prefix="/api")
    app.include_router(providers_router, prefix="/api")
    app.include_router(proxy_router, prefix="/api")
    app.include_router(ui_router, prefix="/api")

    ui_dir = files("authsome.ui").joinpath("web")
    app.mount("/", StaticFiles(directory=str(ui_dir), html=True, check_dir=False), name="ui")

    return app
