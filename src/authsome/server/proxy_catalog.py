"""Proxy route catalog — builds the route table the proxy addon uses to match requests."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from loguru import logger

if TYPE_CHECKING:
    from authsome.server.credential_service import AuthService


def _build_route_entry(definition: Any, connection_name: str) -> dict[str, Any]:
    paths: set[str] = set()
    if definition.oauth:
        for raw_url in [
            definition.oauth.authorization_url,
            definition.oauth.token_url,
            definition.oauth.revocation_url,
            definition.oauth.device_authorization_url,
            (definition.registration.registration_endpoint if definition.registration else None),
        ]:
            if not raw_url:
                continue
            parsed = urlparse(raw_url)
            paths.add(parsed.path or "/")
    return {
        "provider": definition.name,
        "connection": connection_name,
        "api_url": definition.api_url,
        "auth_endpoint_paths": sorted(list(paths)),
    }


async def build_proxy_routes(auth: AuthService, scope: str = "connected") -> dict[str, Any]:
    """Build the list of routes for proxy routing.

    The *scope* argument is supplied by the caller-local proxy addon
    (which owns the configured ``ClientConfig.proxy_mode``). The daemon
    does not persist any proxy mode of its own.
    """
    if scope not in {"connected", "configured"}:
        logger.warning("Unknown proxy scope {!r}, falling back to 'connected'", scope)
        scope = "connected"

    routes = []
    if scope == "connected":
        for provider_group in await auth.list_connections():
            provider_name = provider_group["name"]
            selected_connections = provider_group["connections"]

            try:
                definition = await auth.get_provider(provider_name)
            except Exception:
                continue
            if not definition.api_url:
                continue

            default_conn = next((c for c in selected_connections if c.get("is_default")), None)
            if not default_conn:
                continue

            routes.append(_build_route_entry(definition, default_conn.get("connection_name", "default")))
    else:  # configured
        for definition in await auth.list_providers():
            if not definition.api_url:
                continue
            connection = await auth.resolve_connection_name(definition.name)
            routes.append(_build_route_entry(definition, connection))

    routes.sort(key=lambda r: (r["api_url"].startswith("regex:"), r["provider"]))
    return {"routes": routes}
