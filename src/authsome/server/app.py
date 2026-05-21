"""FastAPI app factory for the Authsome daemon."""

from __future__ import annotations

from contextlib import asynccontextmanager
from importlib.resources import files

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from authsome import audit
from authsome.auth import AuthService
from authsome.auth.sessions import AuthSessionStore
from authsome.errors import AuthsomeError
from authsome.identity.proof import ReplayCache
from authsome.identity.registry import IdentityRegistrationError, IdentityRegistry
from authsome.paths import get_server_log_path
from authsome.server.analytics import init_posthog, shutdown_posthog
from authsome.server.dependencies import (
    create_app_store,
    create_identity_bootstrap_service,
    create_identity_claim_registry,
    create_ownership_resolver,
    create_vault,
    get_deployment_mode,
    get_identity_registry_path,
    get_server_base_url,
    load_server_config,
    load_ui_session_signing_secret,
)
from authsome.server.routes.auth import router as auth_router
from authsome.server.routes.connections import router as connections_router
from authsome.server.routes.health import router as health_router
from authsome.server.routes.identities import router as identities_router
from authsome.server.routes.providers import router as providers_router
from authsome.server.routes.proxy import router as proxy_router
from authsome.server.routes.ui import router as ui_router
from authsome.server.ui_sessions import UiSessionStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage daemon lifecycle."""
    app.state.store = await create_app_store()
    app.state.server_config = load_server_config(app.state.store.home)
    audit.setup(get_server_log_path(app.state.store.home))
    app.state.vault = await create_vault(app.state.store)
    app.state.auth_service = AuthService(
        vault=app.state.vault,
        identity="server",
        deployment_mode=get_deployment_mode(),
    )
    app.state.auth_sessions = AuthSessionStore()
    app.state.ui_sessions = UiSessionStore(load_ui_session_signing_secret(app.state.vault.home))
    app.state.proof_replay_cache = ReplayCache()
    app.state.identity_registry = IdentityRegistry(get_identity_registry_path(app.state.store.home))
    app.state.identity_claim_registry = create_identity_claim_registry(app.state.store.home)
    app.state.server_base_url = get_server_base_url()
    init_posthog()
    app.state.identity_bootstrap = create_identity_bootstrap_service(
        app.state.identity_registry,
        app.state.ui_sessions,
        home=app.state.store.home,
        server_base_url=app.state.server_base_url,
    )
    app.state.ownership_resolver = create_ownership_resolver(app.state.store.home)
    app.state.ownership_cache = {}
    yield
    shutdown_posthog()
    audit.clear()
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
                "message": str(exc),
                "provider": exc.provider,
                "operation": exc.operation,
            },
        )

    @app.exception_handler(IdentityRegistrationError)
    def identity_registration_error_handler(request: Request, exc: IdentityRegistrationError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"error": "IdentityRegistrationError", "message": str(exc)})

    app.include_router(health_router)
    app.include_router(identities_router)
    app.include_router(auth_router)
    app.include_router(connections_router)
    app.include_router(providers_router)
    app.include_router(proxy_router)
    app.include_router(ui_router)

    static_dir = files("authsome.ui").joinpath("static")
    app.mount("/ui/static", StaticFiles(directory=str(static_dir)), name="ui-static")

    @app.get("/ui", include_in_schema=False)
    def _ui_redirect() -> RedirectResponse:
        return RedirectResponse(url="/ui/")

    return app
