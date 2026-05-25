"""Mitmproxy addon and server lifecycle for header injection."""

from __future__ import annotations

import asyncio
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

from loguru import logger
from mitmproxy import ctx as mitmproxy_ctx
from mitmproxy import http
from mitmproxy.options import Options
from mitmproxy.tools.dump import DumpMaster

from authsome import audit
from authsome.cli.client_config import ProxyMode
from authsome.proxy.router import RouteMatch, RouteResolution
from authsome.server.urls import DEFAULT_SERVER_BASE_URL
from authsome.utils import utc_now

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
_HEADER_REFRESH_WINDOW = timedelta(seconds=300)
_REGEX_HOST_PREFIX = "regex:"
_HOST_SPECIFICITY_REGEX = 0
_HOST_SPECIFICITY_EXACT = 1


class ProxyClient(Protocol):
    async def list_connections(self) -> Any: ...

    async def get_provider(self, provider: str) -> Any: ...

    async def resolve_credentials(self, **kwargs: Any) -> Any: ...

    async def proxy_routes(self, scope: str = "connected") -> Any: ...


@dataclass(frozen=True)
class _RouteTarget:
    match: RouteMatch
    path_prefix: str | None
    auth_endpoint_paths: frozenset[str]
    host_specificity: int


@dataclass(frozen=True)
class _RegexRouteTarget:
    host_pattern: re.Pattern[str]
    target: _RouteTarget


@dataclass(frozen=True)
class _HeaderCacheEntry:
    headers: dict[str, str]
    expires_at: datetime | None


class ProxyRouter:
    """Cached provider route table for proxy request matching."""

    def __init__(
        self,
        routes_by_host: dict[str, tuple[_RouteTarget, ...]],
        regex_routes: tuple[_RegexRouteTarget, ...],
    ) -> None:
        self._routes_by_host = routes_by_host
        self._regex_routes = regex_routes

    @classmethod
    async def create(cls, client: ProxyClient, scope: str = "connected") -> ProxyRouter:
        """Async factory for ProxyRouter."""
        routes_by_host, regex_routes = await cls._build_routes(client, scope)
        return cls(routes_by_host, regex_routes)

    def resolve(self, scheme: str, host: str, port: int, path: str) -> RouteResolution:
        """Resolve a route and classify HTTPS misses for audit logging."""
        if scheme.lower() != "https":
            return RouteResolution(None, None)

        normalized_host = _normalize_host(host)
        if normalized_host in _LOOPBACK_HOSTS:
            return RouteResolution(None, None)

        request_path = _request_path(path)
        candidate_targets = list(self._routes_by_host.get(normalized_host, ()))
        candidate_targets.extend(
            route.target for route in self._regex_routes if route.host_pattern.fullmatch(normalized_host)
        )

        matching_targets = [
            target
            for target in candidate_targets
            if _path_matches_prefix(request_path, target.path_prefix) and request_path not in target.auth_endpoint_paths
        ]

        if len(matching_targets) == 0:
            return RouteResolution(None, "no_match")

        best_specificity = max(_target_specificity(target) for target in matching_targets)
        best_targets = [target for target in matching_targets if _target_specificity(target) == best_specificity]

        if len(best_targets) > 1:
            logger.error(
                "Ambiguous proxy match for https://{}:{}{} — matched connections: {}. Forwarding unchanged.",
                normalized_host,
                port,
                path,
                ", ".join(f"{target.match.provider}/{target.match.connection}" for target in best_targets),
            )
            return RouteResolution(None, "ambiguous")
        return RouteResolution(best_targets[0].match, None)

    def route(self, scheme: str, host: str, port: int, path: str) -> RouteMatch | None:
        """Return a route for a request, or None when the request should pass through."""
        return self.resolve(scheme, host, port, path).match

    @staticmethod
    async def _build_routes(
        client: ProxyClient,
        scope: str = "connected",
    ) -> tuple[dict[str, tuple[_RouteTarget, ...]], tuple[_RegexRouteTarget, ...]]:
        routes_by_host: dict[str, list[_RouteTarget]] = {}
        regex_routes: list[_RegexRouteTarget] = []
        from authsome.auth.models.provider import ProviderDefinition

        if hasattr(client, "proxy_routes"):
            try:
                route_data = await client.proxy_routes(scope=scope)
                if not isinstance(route_data, dict):
                    raise TypeError("proxy_routes() must return a dict payload")
                for route in route_data.get("routes", []):
                    route_match = RouteMatch(provider=route["provider"], connection=route.get("connection"))
                    regex_pattern = _compile_host_regex(route["api_url"])
                    auth_paths = frozenset(route.get("auth_endpoint_paths", []))
                    if regex_pattern is not None:
                        regex_routes.append(
                            _RegexRouteTarget(
                                host_pattern=regex_pattern,
                                target=_RouteTarget(
                                    match=route_match,
                                    path_prefix=None,
                                    auth_endpoint_paths=auth_paths,
                                    host_specificity=_HOST_SPECIFICITY_REGEX,
                                ),
                            )
                        )
                        continue
                    host, path_prefix = _parse_api_url(route["api_url"])
                    if not host or host in _LOOPBACK_HOSTS:
                        continue
                    routes_by_host.setdefault(host, []).append(
                        _RouteTarget(
                            match=route_match,
                            path_prefix=path_prefix,
                            auth_endpoint_paths=auth_paths,
                            host_specificity=_HOST_SPECIFICITY_EXACT,
                        )
                    )
                return {host: tuple(routes) for host, routes in routes_by_host.items()}, tuple(regex_routes)
            except Exception as exc:
                logger.warning("Could not load daemon proxy routes, falling back to local route build: {}", exc)

        connections_data = await client.list_connections()
        if isinstance(connections_data, list):
            connections_data = {"connections": connections_data}
        for provider_group in connections_data["connections"]:
            provider_name = provider_group["name"]
            selected_connections = provider_group["connections"]

            try:
                definition_dict = await client.get_provider(provider_name)
                if isinstance(definition_dict, dict):
                    definition = ProviderDefinition.model_validate(definition_dict)
                else:
                    definition = definition_dict
            except Exception as exc:
                logger.warning("Skipping proxy routes for provider {}: {}", provider_name, exc)
                continue

            for conn in selected_connections:
                if conn.get("is_default") is False:
                    continue
                target_api_url = conn.get("api_url") or getattr(definition, "api_url", None)
                if not target_api_url:
                    continue

                resolved = definition.resolve_urls(conn.get("base_url"))
                route_match = RouteMatch(provider=provider_name, connection=conn.get("connection_name"))
                regex_pattern = _compile_host_regex(target_api_url)
                if regex_pattern is not None:
                    regex_routes.append(
                        _RegexRouteTarget(
                            host_pattern=regex_pattern,
                            target=_RouteTarget(
                                match=route_match,
                                path_prefix=None,
                                auth_endpoint_paths=_auth_endpoint_paths_for_regex(resolved, regex_pattern),
                                host_specificity=_HOST_SPECIFICITY_REGEX,
                            ),
                        )
                    )
                    continue

                host, path_prefix = _parse_api_url(target_api_url)
                if not host or host in _LOOPBACK_HOSTS:
                    continue

                auth_endpoint_paths = _auth_endpoint_paths(resolved, host)
                routes_by_host.setdefault(host, []).append(
                    _RouteTarget(
                        match=route_match,
                        path_prefix=path_prefix,
                        auth_endpoint_paths=auth_endpoint_paths,
                        host_specificity=_HOST_SPECIFICITY_EXACT,
                    )
                )

        return {host: tuple(routes) for host, routes in routes_by_host.items()}, tuple(regex_routes)


async def _route(client: ProxyClient, scheme: str, host: str, port: int, path: str) -> RouteMatch | None:
    """Return a RouteMatch when exactly one connected provider matches the request.

    Returns None for loopback targets, OAuth endpoints, zero matches, or ambiguous matches.
    """
    router = await ProxyRouter.create(client)
    return router.route(scheme, host, port, path)


def _is_auth_endpoint(provider, host: str, path: str) -> bool:
    return _request_path(path) in _auth_endpoint_paths(provider, _normalize_host(host))


def _extract_host(api_url: str) -> str:
    return _parse_api_url(api_url)[0]


def _parse_api_url(api_url: str) -> tuple[str, str | None]:
    raw = api_url.strip()
    parsed = urlparse(raw if "://" in raw else f"//{raw}")
    host = _normalize_host(parsed.hostname or raw)
    return host, _normalize_path_prefix(parsed.path)


def _compile_host_regex(api_url: str) -> re.Pattern[str] | None:
    raw = api_url.strip()
    if not raw.lower().startswith(_REGEX_HOST_PREFIX):
        return None

    pattern = raw[len(_REGEX_HOST_PREFIX) :].strip()
    if not pattern:
        logger.warning("Skipping empty regex api_url")
        return None
    try:
        return re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        logger.warning("Skipping invalid regex api_url {}: {}", pattern, exc)
        return None


def _normalize_host(host: str) -> str:
    return host.strip().strip("[]").lower()


def _request_path(path: str) -> str:
    return urlparse(path).path or "/"


def _normalize_path_prefix(path: str | None) -> str | None:
    if not path or path == "/":
        return None
    return path.rstrip("/")


def _path_matches_prefix(request_path: str, path_prefix: str | None) -> bool:
    if path_prefix is None:
        return True
    return request_path == path_prefix or request_path.startswith(f"{path_prefix}/")


def _path_prefix_specificity(path_prefix: str | None) -> int:
    return len(path_prefix or "")


def _target_specificity(target: _RouteTarget) -> tuple[int, int]:
    return _path_prefix_specificity(target.path_prefix), target.host_specificity


def _auth_endpoint_paths(provider, host: str) -> frozenset[str]:
    if not provider.oauth:
        return frozenset()

    paths: set[str] = set()
    for raw_url in [
        provider.oauth.authorization_url,
        provider.oauth.token_url,
        provider.oauth.revocation_url,
        provider.oauth.device_authorization_url,
    ]:
        if not raw_url:
            continue
        parsed = urlparse(raw_url)
        if parsed.hostname and _normalize_host(parsed.hostname) == host:
            paths.add(parsed.path or "/")
    return frozenset(paths)


def _auth_endpoint_paths_for_regex(provider, host_pattern: re.Pattern[str]) -> frozenset[str]:
    if not provider.oauth:
        return frozenset()

    paths: set[str] = set()
    for raw_url in [
        provider.oauth.authorization_url,
        provider.oauth.token_url,
        provider.oauth.revocation_url,
        provider.oauth.device_authorization_url,
    ]:
        if not raw_url:
            continue
        parsed = urlparse(raw_url)
        if parsed.hostname and host_pattern.fullmatch(_normalize_host(parsed.hostname)):
            paths.add(parsed.path or "/")
    return frozenset(paths)


class AuthProxyAddon:
    """Mitmproxy addon that injects auth headers for matched requests.

    The proxy mode is caller-local config (`ClientConfig.proxy_mode`),
    read once by the runner and injected here at construction time —
    the daemon never sees or persists a proxy mode of its own.
    """

    def __init__(self, client: ProxyClient, mode: ProxyMode = "connected_allow") -> None:
        self._client = client
        self._mode = mode
        self._scope, self._policy = mode.split("_", 1)
        self._router: ProxyRouter | None = None
        self._header_cache: dict[tuple[str, str], _HeaderCacheEntry] = {}
        self._header_locks: dict[tuple[str, str], asyncio.Lock] = {}

    async def _ensure_initialized(self) -> ProxyRouter:
        """Build the router once on the first request."""
        if self._router is None:
            self._router = await ProxyRouter.create(self._client, scope=self._scope)
        return self._router

    async def request(self, flow: http.HTTPFlow) -> None:
        router = await self._ensure_initialized()
        policy = self._policy

        resolution = router.resolve(flow.request.scheme, flow.request.host, flow.request.port, flow.request.path)
        if resolution.match is None:
            if resolution.miss_reason == "no_match" and policy == "deny":
                self._deny_request(flow, "no_match")
            elif resolution.miss_reason is not None:
                normalized_host = _normalize_host(flow.request.host)
                logger.info(
                    "client_event event=proxy_miss host={} reason={} method={} path={}",
                    normalized_host,
                    resolution.miss_reason,
                    flow.request.method,
                    flow.request.path,
                )
                logger.debug(
                    "Proxy miss: host={} reason={} {} {}",
                    normalized_host,
                    resolution.miss_reason,
                    flow.request.method,
                    flow.request.path,
                )
            return

        match = resolution.match
        try:
            headers = await self._get_auth_headers(match)
        except Exception as exc:
            normalized_host = _normalize_host(flow.request.host)
            audit.log(
                "proxy_no_credentials",
                host=normalized_host,
                provider=match.provider,
                connection=match.connection,
            )
            logger.warning(
                "No credentials for provider={} connection={} host={}: {}",
                match.provider,
                match.connection,
                normalized_host,
                exc,
            )
            if policy == "deny":
                self._deny_request(flow, "no_credentials", match=match)
            return

        for key, value in headers.items():
            flow.request.headers[key] = value

        logger.info(
            "client_event event=proxy_inject provider={} connection={} host={} method={} path={}",
            match.provider,
            match.connection,
            _normalize_host(flow.request.host),
            flow.request.method,
            flow.request.path,
        )

    def _deny_request(
        self,
        flow: http.HTTPFlow,
        reason: str,
        *,
        match: RouteMatch | None = None,
    ) -> None:
        host = _normalize_host(flow.request.host)
        audit.log("proxy_deny", host=host, reason=reason)
        logger.warning("Proxy deny: host={} reason={}", host, reason)
        if flow.request.method.upper() == "CONNECT":
            flow.kill()
            return
        flow.response = http.Response.make(403, _deny_body(reason, match).encode("utf-8"))

    async def _get_auth_headers(self, match: RouteMatch) -> dict[str, str]:
        cache_key = (match.provider, match.connection or "")
        now = utc_now()
        cached = self._header_cache.get(cache_key)
        if cached and _header_cache_valid(cached, now):
            return cached.headers.copy()

        lock = self._header_locks.get(cache_key)
        if lock is None:
            lock = asyncio.Lock()
            self._header_locks[cache_key] = lock

        async with lock:
            now = utc_now()
            cached = self._header_cache.get(cache_key)
            if cached and _header_cache_valid(cached, now):
                return cached.headers.copy()

            # Resolve through runtime client
            headers_resp = await self._client.resolve_credentials(
                provider=match.provider,
                connection=match.connection,
            )
            headers = headers_resp["headers"]
            expires_at_raw = headers_resp.get("expires_at")
            expires_at = (
                datetime.fromisoformat(expires_at_raw.replace("Z", "+00:00"))
                if isinstance(expires_at_raw, str)
                else expires_at_raw
            )

            self._header_cache[cache_key] = _HeaderCacheEntry(
                headers=headers.copy(),
                expires_at=expires_at,
            )
            return headers


def _deny_body(reason: str, match: RouteMatch | None) -> str:
    """Build a human-readable 403 body for a denied proxy request.

    For `no_credentials` we surface the provider name plus a CLI command
    and a dashboard URL so the agent (or human) can recover; other
    reasons fall back to a generic message.

    The dashboard URL uses ``DEFAULT_SERVER_BASE_URL``. It still requires an active dashboard session
    to land on the connect screen directly.
    """
    if reason == "no_credentials" and match is not None:
        provider = match.provider
        return (
            f"Forbidden: provider '{provider}' is configured but has no "
            f"active connection. Run `authsome login {provider}` to connect, "
            f"or visit {DEFAULT_SERVER_BASE_URL}/ui/apps/{provider}."
        )
    return "Forbidden by Authsome proxy policy"


def _header_cache_valid(entry: _HeaderCacheEntry, now: datetime) -> bool:
    if entry.expires_at is None:
        return True
    return now < entry.expires_at - _HEADER_REFRESH_WINDOW


class RunningProxy:
    """Handle for a proxy running in a background thread."""

    def __init__(self, url: str, master: DumpMaster, thread: threading.Thread, confdir: Path) -> None:
        self.url = url
        self.master = master
        self.thread = thread
        self.confdir = confdir

    @property
    def ca_cert_path(self) -> Path:
        """Path to the mitmproxy CA certificate (PEM format)."""
        return self.confdir / "mitmproxy-ca-cert.pem"

    def shutdown(self) -> None:
        self.master.shutdown()
        self.thread.join(timeout=5)


class _ProxyReadyAddon:
    def __init__(self, ready: threading.Event, state: dict, host: str, port: int) -> None:
        self._ready = ready
        self._state = state
        self._host = host
        self._port = port

    def running(self) -> None:
        bound_host, bound_port = _resolve_listen_address(self._host, self._port)
        self._state["url"] = f"http://{_format_proxy_url_host(bound_host)}:{bound_port}"
        self._ready.set()


def _resolve_listen_address(fallback_host: str, fallback_port: int) -> tuple[str, int]:
    master = getattr(mitmproxy_ctx, "master", None)
    proxyserver = master.addons.get("proxyserver") if master else None
    listen_addrs = proxyserver.listen_addrs() if proxyserver else []
    if not listen_addrs:
        return fallback_host, fallback_port

    host, port = listen_addrs[0]
    if host in {"", "0.0.0.0", "::"}:
        host = fallback_host or "127.0.0.1"
    return str(host), int(port)


def _format_proxy_url_host(host: str) -> str:
    return f"[{host}]" if ":" in host and not host.startswith("[") else host


def _build_proxy_options(host: str, port: int, confdir: Path) -> Options:
    return Options(
        listen_host=host,
        listen_port=port,
        ssl_insecure=False,
        confdir=str(confdir),
    )


def start_proxy_server(
    client: ProxyClient,
    host: str = "127.0.0.1",
    port: int = 0,
    *,
    mode: ProxyMode = "connected_allow",
) -> RunningProxy:
    """Start a mitmproxy DumpMaster in a background thread."""
    from typing import get_args

    if mode not in get_args(ProxyMode):
        raise ValueError(f"Invalid proxy mode {mode!r}, expected one of {get_args(ProxyMode)}")

    confdir = Path.home() / ".mitmproxy"
    auth_addon = AuthProxyAddon(client=client, mode=mode)

    ready = threading.Event()
    state: dict = {}

    def _run() -> None:
        async def _async_main() -> None:
            opts = _build_proxy_options(host, port, confdir)
            master = DumpMaster(opts, with_termlog=False, with_dumper=False)
            master.addons.add(auth_addon)
            master.addons.add(_ProxyReadyAddon(ready=ready, state=state, host=host, port=port))
            state["master"] = master
            await master.run()

        try:
            asyncio.run(_async_main())
        except Exception as exc:
            state["error"] = exc
            ready.set()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    if not ready.wait(timeout=10):
        raise RuntimeError("Proxy server failed to initialize within 10 s")
    if "error" in state:
        raise RuntimeError("Proxy server failed to initialize") from state["error"]
    if "master" not in state or "url" not in state:
        raise RuntimeError("Proxy server failed to publish its listen address")

    url = state["url"]
    logger.info("Proxy server listening on {}", url)
    return RunningProxy(url=url, master=state["master"], thread=thread, confdir=confdir)
