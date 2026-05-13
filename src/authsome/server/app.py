"""FastAPI app factory for the Authsome daemon."""

from __future__ import annotations

from contextlib import asynccontextmanager
from importlib.resources import files

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from authsome.auth import AuthService
from authsome.auth.sessions import AuthSessionStore
from authsome.errors import AuthsomeError
from authsome.identity.proof import ReplayCache
from authsome.identity.registry import IdentityRegistrationError, IdentityRegistry
from authsome.server.dependencies import create_vault, get_server_base_url, get_server_home
from authsome.server.routes.auth import router as auth_router
from authsome.server.routes.connections import router as connections_router
from authsome.server.routes.health import router as health_router
from authsome.server.routes.identities import router as identities_router
from authsome.server.routes.providers import router as providers_router
from authsome.server.routes.proxy import router as proxy_router
from authsome.server.routes.ui import router as ui_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage daemon lifecycle."""
    app.state.vault = await create_vault()
    app.state.auth_service = AuthService(vault=app.state.vault, identity="server")
    app.state.auth_sessions = AuthSessionStore()
    app.state.proof_replay_cache = ReplayCache()
    app.state.identity_registry = IdentityRegistry(get_server_home(app.state.vault.home))
    app.state.server_base_url = get_server_base_url()
    yield


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
