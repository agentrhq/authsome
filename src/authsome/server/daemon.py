"""Local daemon foreground runner."""

from __future__ import annotations

import uvicorn

from authsome.server.config import get_server_config

# Settings-backed defaults, retained as module constants for the CLI daemon command.
DEFAULT_HOST = get_server_config().host
DEFAULT_PORT = get_server_config().port


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
