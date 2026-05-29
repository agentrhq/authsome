"""FastAPI app factory for the Authsome daemon."""

from __future__ import annotations

from contextlib import asynccontextmanager
from importlib.resources import files

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from authsome.auth.sessions import AuthSessionStore
from authsome.errors import AuthsomeError
from authsome.identity.proof import ReplayCache
from authsome.server.analytics import init_posthog, shutdown_posthog
from authsome.server.audit import configure_server_audit_log
from authsome.server.dependencies import (
    create_hosted_account_service,
    create_identity_bootstrap_service,
    create_ownership_resolver,
    create_store,
    create_vault,
    get_server_audit_db_path,
    get_server_base_url,
    load_server_config,
    load_ui_session_signing_secret,
)
from authsome.server.provider_repository import ProviderRepository
from authsome.server.routes.audit import router as audit_router
from authsome.server.routes.auth import router as auth_router
from authsome.server.routes.connections import router as connections_router
from authsome.server.routes.health import router as health_router
from authsome.server.routes.identities import router as identities_router
from authsome.server.routes.providers import router as providers_router
from authsome.server.routes.proxy import router as proxy_router
from authsome.server.routes.ui import UiAuthRequiredError
from authsome.server.routes.ui import router as ui_router
from authsome.server.store.repositories import IdentityRegistrationError
from authsome.server.ui_sessions import UiSessionStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage daemon lifecycle."""
    app.state.store = await create_store()
    app.state.server_config = await load_server_config(app.state.store)
    app.state.audit_log = configure_server_audit_log(get_server_audit_db_path(app.state.store.home))
    app.state.vault = await create_vault(app.state.store.home)
    app.state.auth_sessions = AuthSessionStore()
    app.state.ui_sessions = UiSessionStore(load_ui_session_signing_secret(app.state.store.home))
    app.state.proof_replay_cache = ReplayCache()
    app.state.identity_registry = app.state.store.identity_registry
    app.state.vault_registry = app.state.store.vaults
    app.state.identity_claim_registry = app.state.store.identity_claims
    app.state.principal_vault_binding_registry = app.state.store.principal_vault_bindings
    app.state.provider_repository = ProviderRepository(app.state.store.provider_definitions)
    app.state.hosted_account_service = create_hosted_account_service(app.state.store)
    app.state.server_base_url = get_server_base_url()
    init_posthog()
    app.state.identity_bootstrap = create_identity_bootstrap_service(
        app.state.identity_registry,
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

    app.include_router(health_router)
    app.include_router(identities_router)
    app.include_router(audit_router)
    app.include_router(auth_router)
    app.include_router(connections_router)
    app.include_router(providers_router)
    app.include_router(proxy_router)
    app.include_router(ui_router)

    static_dir = files("authsome.ui").joinpath("static")
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="ui-static")

    return app
