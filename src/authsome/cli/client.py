"""Internal HTTP client used by the CLI and local proxy runner."""

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
from fastapi import status

import authsome.errors as err_mod
from authsome.cli.identity import RuntimeIdentity
from authsome.config import get_authsome_config
from authsome.identity.helpers import generate_handle
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
            if response.status_code == status.HTTP_401_UNAUTHORIZED and data.get("detail") == "Unknown identity handle":
                raise err_mod.IdentityNotRegisteredError("current agent") from exc
            error_name = data.get("error")
            message = data.get("message")
            if error_name and message:
                exc_cls = getattr(err_mod, error_name, None)
                if exc_cls and issubclass(exc_cls, err_mod.AuthsomeError):
                    obj = exc_cls.__new__(exc_cls)
                    Exception.__init__(obj, message)
                    obj.provider = data.get("provider")
                    obj.operation = data.get("operation")
        except httpx.HTTPStatusError:
            raise
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
        self._server_registered = False  # in-memory flag; reset on 401

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
        _retry: bool = True,
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
        if protected and _retry and response.status_code == status.HTTP_401_UNAUTHORIZED:
            try:
                detail = response.json().get("detail", "")
            except Exception:
                detail = ""
            if detail == "Unknown identity handle":
                self._server_registered = False
                await self.ensure_identity_ready()
                return await self._request(method, path, body=body, timeout=timeout, protected=protected, _retry=False)
        raise_for_error(response)
        return response.json()

    async def _proof_headers(self, method: str, path: str, body: bytes) -> dict[str, str]:
        identity = await self.ensure_identity_ready()
        if identity.handle is None:
            raise RuntimeError("Identity handle could not be resolved from the identity server")
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
        """Ensure the acting identity is registered with the server and claimed.

        Checks server status on the first call per client instance (cached in
        memory after that). Registers and opens the browser claim URL when the
        identity is new or the server has been reset.
        """
        runtime = self._runtime_identity()
        if self._server_registered:
            return runtime
        if runtime.handle is None:
            runtime = await self._resolve_env_identity(runtime)
            self._identity = runtime
        runtime = await self._check_server_registration(runtime)
        self._identity = runtime
        self._server_registered = True
        return runtime

    def _runtime_identity(self) -> RuntimeIdentity:
        if self._identity is None:
            self._identity = RuntimeIdentity.load(self._home)
        return self._identity

    async def _resolve_env_identity(self, runtime: RuntimeIdentity) -> RuntimeIdentity:
        """Resolve a handle-less env identity's handle from the identity server.

        Looks up the handle bound to the DID. When the DID is unknown the agent
        is brand new, so a handle is generated; the existing registration/claim
        flow then registers it.
        """
        handle = await self.resolve_handle_by_did(runtime.did)
        if handle is None:
            handle = generate_handle()
        return runtime.model_copy(update={"handle": handle})

    async def _check_server_registration(self, runtime: RuntimeIdentity) -> RuntimeIdentity:
        """Verify registration with the server; register and claim if needed."""
        handle = runtime.handle
        if handle is None:
            raise RuntimeError("Identity handle could not be resolved from the identity server")
        try:
            identity_status = await self.get_identity_status(handle)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != status.HTTP_404_NOT_FOUND:
                raise
            try:
                identity_status = await self.register_identity(handle, runtime.did)
            except httpx.HTTPStatusError as reg_exc:
                if reg_exc.response.status_code != status.HTTP_409_CONFLICT:
                    raise
                resolved_handle = await self.resolve_handle_by_did(runtime.did)
                if resolved_handle is None:
                    raise
                handle = resolved_handle
                runtime = runtime.model_copy(update={"handle": handle})
                identity_status = await self.get_identity_status(handle)

        reg_status = identity_status.get("registration_status", "")
        if reg_status == "claim_required":
            claim_url = identity_status.get("claim_url", "")
            if claim_url:
                self._open_claim_url(claim_url)
            await self._poll_claim_completion(handle)
        elif reg_status == "rejected":
            raise RuntimeError(f"Agent '{handle}' claim was rejected by the server")
        return runtime

    def _open_claim_url(self, claim_url: str) -> None:
        print(f"Open this URL in your browser to claim this agent:\n  {claim_url}", file=sys.stderr)
        with suppress(Exception):
            webbrowser.open(claim_url)

    async def _poll_claim_completion(self, handle: str, *, timeout_seconds: int = 300) -> None:
        print("Waiting for agent to be claimed...", file=sys.stderr)
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        while True:
            status = await self.get_identity_status(handle)
            reg_status = status.get("registration_status", "")
            if reg_status == "claimed":
                return
            if reg_status == "rejected":
                raise RuntimeError(f"Agent '{handle}' claim was rejected")
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError(f"Timed out waiting for agent '{handle}' to be claimed")
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

    async def set_global_connection(self, provider: str, connection_name: str) -> dict[str, Any]:
        return await self._post(f"{API_PREFIX}/connections/{provider}/{connection_name}/global")

    async def unset_global_connection(self, provider: str) -> dict[str, Any]:
        return await self._delete(f"{API_PREFIX}/connections/{provider}/global")

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

    async def resolve_handle_by_did(self, did: str) -> str | None:
        """Return the handle the identity server has bound to ``did``, or None if unknown."""
        try:
            payload = await self._get(f"{API_PREFIX}/identities/by-did/{did}", protected=False)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == status.HTTP_404_NOT_FOUND:
                return None
            raise
        return payload.get("identity")

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
