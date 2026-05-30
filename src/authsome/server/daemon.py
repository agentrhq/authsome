"""Local daemon foreground runner."""

from __future__ import annotations

import uvicorn

from authsome.server.settings import get_settings

# Settings-backed defaults, retained as module constants for the CLI daemon command.
DEFAULT_HOST = get_settings().host
DEFAULT_PORT = get_settings().port


def serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, reload: bool = False) -> None:
    """Run the daemon in the foreground."""
    uvicorn.run(
        "authsome.server.app:create_app",
        host=host,
        port=port,
        log_level="info",
        reload=reload,
        factory=True,
        reload_includes=["*.py", "*.json", "*.html", "*.css", "*.js"],
    )
