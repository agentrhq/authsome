"""Internal HTTP client used by the CLI and local proxy runner."""

from __future__ import annotations

import asyncio
import json
import sys
import webbrowser
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from authsome.cli.identity import (
    IdentitySource,
    RuntimeIdentity,
    load_identity,
    load_private_key,
    load_runtime_identity,
    mark_registered,
)
from authsome.config import get_authsome_config
from authsome.identity.proof import POP_AUTH_SCHEME, create_proof_jwt
from authsome.server.config import get_server_config

API_PREFIX = "/api"


def resolve_daemon_url(env: Mapping[str, str] | None = None) -> str:
    """Return the top-level configured Authsome server URL."""
    configured = get_authsome_config().base_url
    raw = (env or {}).get("AUTHSOME_BASE_URL", configured).strip()
    return raw.rstrip("/") or configured


def is_local_daemon_url(url: str) -> bool:
    """Return whether the configured daemon URL targets a local loopback daemon."""
    hostname = urlparse(url).hostname
    return hostname in {"127.0.0.1", "localhost", "::1"}


def is_managed_local_daemon_url(url: str) -> bool:
    """Return whether the URL matches the default local daemon managed by the CLI."""
    parsed = urlparse(url)
    if parsed.scheme != "http":
        return False
    if parsed.path not in {"", "/"}:
        return False
    return parsed.hostname in {"127.0.0.1", "localhost", "::1"} and (parsed.port in {None, get_server_config().port})


def raise_for_error(response: httpx.Response) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        obj = None
        try:
            data = response.json()
            error_name = data.get("error")
            message = data.get("message")
            if error_name and message:
                import authsome.errors as err_mod

                exc_cls = getattr(err_mod, error_name, None)
                if exc_cls and issubclass(exc_cls, err_mod.AuthsomeError):
                    obj = exc_cls.__new__(exc_cls)
                    Exception.__init__(obj, message)
                    obj.provider = data.get("provider")
                    obj.operation = data.get("operation")
        except Exception:
            pass

        if obj is not None:
            raise obj from exc

        raise exc


class AuthsomeApiClient:
    """Small typed wrapper around the daemon API."""

    def __init__(
        self,
        base_url: str | None = None,
        identity: RuntimeIdentity | None = None,
        home: Path | None = None,
    ) -> None:
        self._base_url = (base_url or resolve_daemon_url()).rstrip("/")
        self._home = home or get_authsome_config().home
        self._identity = identity

    @property
    def base_url(self) -> str:
        return self._base_url

    async def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        timeout: int = 30,
        protected: bool = True,
    ) -> dict[str, Any]:
        body_bytes = b""
        headers: dict[str, str] = {}
        if body is not None:
            body_bytes = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if protected:
            headers.update(await self._proof_headers(method, path, body_bytes))
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method,
                f"{self._base_url}{path}",
                content=body_bytes if body is not None else None,
                headers=headers,
            )
        raise_for_error(response)
        return response.json()

    def _runtime_identity(self) -> RuntimeIdentity:
        if self._identity is None:
            self._identity = load_runtime_identity(self._home)
        return self._identity

    def _filesystem_runtime_for_handle(self, handle: str) -> RuntimeIdentity:
        identity = load_identity(self._home, handle)
        return RuntimeIdentity(
            handle=identity.handle,
            did=identity.did,
            source=IdentitySource.FILESYSTEM,
            signer=load_private_key(self._home, identity.handle),
        )

    async def _proof_headers(self, method: str, path: str, body: bytes) -> dict[str, str]:
        identity = await self.ensure_identity_ready()
        token = create_proof_jwt(
            private_key=identity.signer,
            issuer=identity.did,
            subject=identity.handle,
            method=method,
            path_query=path,
            body=body,
        )
        return {"Authorization": f"{POP_AUTH_SCHEME} {token}"}

    async def ensure_identity_ready(self) -> RuntimeIdentity:
        """Ensure the acting identity is registered and claimed by a principal.

        A freshly registered identity must be claimed by a principal before it
        can make authenticated calls; the daemon returns a browser claim URL
        which is opened here while we poll for completion.
        """
        runtime = self._runtime_identity()
        if runtime.source is IdentitySource.ENV:
            return await self._ensure_env_identity_ready(runtime)

        identity = load_identity(self._home, runtime.handle)
        if not identity.registered_for(self._base_url):
            await self.register_identity(identity.handle, identity.did)
            identity = mark_registered(self._home, identity.handle, server_url=self._base_url)
        else:
            return runtime

        self._identity = self._filesystem_runtime_for_handle(identity.handle)
        return self._identity

    async def _ensure_env_identity_ready(self, identity: RuntimeIdentity) -> RuntimeIdentity:
        try:
            status = await self.get_identity_status(identity.handle)
        except Exception:
            status = await self.register_identity(identity.handle, identity.did)

        registration_status = status.get("registration_status", "registered")
        if registration_status == "unknown":
            await self.register_identity(identity.handle, identity.did)
        return identity

    def _open_claim_url(self, claim_url: str) -> None:
        """Surface the browser claim URL (so headless users can open it) and try to launch it."""
        print(
            f"Open this URL in your browser to register and claim this identity:\n  {claim_url}",
            file=sys.stderr,
        )
        with suppress(Exception):
            webbrowser.open(claim_url)

    async def _poll_claim_completion(self, handle: str, *, timeout_seconds: int = 300) -> dict[str, Any]:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while True:
            status = await self.get_identity_status(handle)
            if status.get("registration_status") in {"claimed", "registered"}:
                return status
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError(f"Timed out waiting for identity '{handle}' to be claimed")
            await asyncio.sleep(1)

    async def _get(self, path: str, *, protected: bool = True) -> dict[str, Any]:
        return await self._request("GET", path, timeout=10, protected=protected)

    async def _post(self, path: str, body: dict[str, Any] | None = None, *, protected: bool = True) -> dict[str, Any]:
        return await self._request("POST", path, body=body or {}, timeout=30, protected=protected)

    async def _delete(self, path: str, *, protected: bool = True) -> dict[str, Any]:
        return await self._request("DELETE", path, timeout=30, protected=protected)

    async def health(self) -> dict[str, Any]:
        return await self._get(f"{API_PREFIX}/health", protected=False)

    async def ready(self) -> dict[str, Any]:
        return await self._get(f"{API_PREFIX}/ready")

    async def start_login(self, **kwargs: Any) -> dict[str, Any]:
        return await self._post(f"{API_PREFIX}/auth/sessions", kwargs)

    async def get_session(self, session_id: str) -> dict[str, Any]:
        return await self._get(f"{API_PREFIX}/auth/sessions/{session_id}")

    async def resume_login_session(self, session_id: str, **kwargs: Any) -> dict[str, Any]:
        return await self._post(f"{API_PREFIX}/auth/sessions/{session_id}/resume", {"data": kwargs})

    async def list_connections(self) -> dict[str, Any]:
        return await self._get(f"{API_PREFIX}/connections")

    async def get_connection(self, provider: str, connection_name: str = "default") -> dict[str, Any]:
        return await self._get(f"{API_PREFIX}/connections/{provider}/{connection_name}")

    async def logout(self, provider: str, connection_name: str = "default") -> None:
        await self._post(f"{API_PREFIX}/connections/{provider}/{connection_name}/logout")

    async def revoke(self, provider: str) -> None:
        await self._post(f"{API_PREFIX}/connections/{provider}/revoke")

    async def set_default_connection(self, provider: str, connection_name: str) -> None:
        await self._post(f"{API_PREFIX}/connections/{provider}/{connection_name}/default")

    async def get_provider(self, provider: str) -> dict[str, Any]:
        return await self._get(f"{API_PREFIX}/providers/{provider}")

    async def register_provider(self, definition_dict: dict[str, Any], force: bool = False) -> None:
        await self._post(f"{API_PREFIX}/providers", {"definition": definition_dict, "force": force})

    async def list_audit_events(self, *, limit: int = 50) -> dict[str, Any]:
        return await self._get(f"{API_PREFIX}/audit/events?limit={limit}")

    async def record_audit_event(self, event: dict[str, Any]) -> None:
        await self._post(f"{API_PREFIX}/audit/events", {"event": event})

    async def register_identity(self, handle: str, did: str) -> dict[str, Any]:
        return await self._post(f"{API_PREFIX}/identities/register", {"handle": handle, "did": did}, protected=False)

    async def get_identity_status(self, handle: str) -> dict[str, Any]:
        return await self._get(f"{API_PREFIX}/identities/{handle}", protected=False)

    async def remove(self, provider: str) -> None:
        await self._delete(f"{API_PREFIX}/providers/{provider}")

    async def list_providers_by_source(self) -> dict[str, Any]:
        return await self._get(f"{API_PREFIX}/providers")

    async def export(self, provider: str | None = None, connection_name: str = "default", format: str = "env") -> str:
        result = await self._post(
            f"{API_PREFIX}/credentials/export",
            {"provider": provider, "connection": connection_name, "format": format},
        )
        return result["output"]

    async def proxy_routes(self, scope: str = "connected") -> dict[str, Any]:
        """Return proxy routes from a PoP-protected daemon endpoint.

        The scope is owned by the caller (read from `ClientConfig.proxy_mode`);
        the daemon merely projects its connections/providers into the
        requested view.
        """
        return await self._get(f"{API_PREFIX}/proxy/routes?scope={scope}")

    async def resolve_credentials(self, **kwargs: Any) -> dict[str, Any]:
        """Resolve proxy credentials from a PoP-protected daemon endpoint."""
        return await self._post(f"{API_PREFIX}/credentials/resolve", kwargs)

    async def whoami(self) -> dict[str, Any]:
        return await self._get(f"{API_PREFIX}/whoami")

    async def doctor(self) -> dict[str, Any]:
        return await self.ready()

    async def start_ui_session(self) -> dict[str, Any]:
        return await self._post(f"{API_PREFIX}/session")
