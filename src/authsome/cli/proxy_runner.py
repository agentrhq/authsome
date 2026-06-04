"""CLI subprocess runner for commands launched behind the local auth proxy."""

import os
import subprocess
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any, Protocol

from loguru import logger

from authsome.cli.config import load_client_config, save_client_config
from authsome.config import get_authsome_config
from authsome.proxy.certs import ensure_local_proxy_ca
from authsome.proxy.server import RunningProxy, start_proxy_server


class ProxyClient(Protocol):
    async def list_connections(self) -> Any: ...

    async def get_provider(self, provider: str) -> Any: ...

    async def resolve_credentials(self, **kwargs: Any) -> Any: ...

    async def proxy_routes(self, scope: str = "connected") -> Any: ...

    async def list_providers_by_source(self) -> Any: ...

    async def record_audit_event(self, event: dict[str, Any]) -> Any: ...


class ProxyRunner:
    """Launch a subprocess behind the Authsome local auth proxy."""

    def __init__(self, client: ProxyClient, home: Path | None = None) -> None:
        self._client = client
        self._home = home or get_authsome_config().home

    async def run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        """Run *command* behind the auth-injecting proxy."""
        proxy_url, server = self._start_proxy()
        env = os.environ.copy()
        env["HTTP_PROXY"] = proxy_url
        env["HTTPS_PROXY"] = proxy_url
        env["http_proxy"] = proxy_url
        env["https_proxy"] = proxy_url
        existing_no_proxy = ",".join(filter(None, [env.get("NO_PROXY", ""), env.get("no_proxy", "")]))
        no_proxy = self._merge_no_proxy(existing_no_proxy)
        env["NO_PROXY"] = no_proxy
        env["no_proxy"] = no_proxy
        env["AUTHSOME_PROXY_MODE"] = "true"

        await self._inject_dummy_credentials(env)

        ca_bundle_path = self._build_ca_bundle(server)
        if ca_bundle_path:
            env["SSL_CERT_FILE"] = str(ca_bundle_path)
            env["REQUESTS_CA_BUNDLE"] = str(ca_bundle_path)
            env["CURL_CA_BUNDLE"] = str(ca_bundle_path)
            env["GIT_SSL_CAINFO"] = str(ca_bundle_path)
            env["NODE_EXTRA_CA_CERTS"] = str(server.ca_cert_path)
            logger.debug("CA bundle injected: {}", ca_bundle_path)

        try:
            return subprocess.run(command, env=env, capture_output=False, text=True, check=False)
        finally:
            server.shutdown()
            if ca_bundle_path and ca_bundle_path.exists():
                with suppress(OSError):
                    ca_bundle_path.unlink()

    def _start_proxy(self) -> tuple[str, RunningProxy]:
        self._ensure_local_proxy_ca_once()
        mode = load_client_config(self._home).proxy_mode
        server = start_proxy_server(self._client, mode=mode, dashboard_url=get_authsome_config().base_url)
        return server.url, server

    def _ensure_local_proxy_ca_once(self) -> None:
        config = load_client_config(self._home)
        if config.proxy_ca_installed:
            return
        if ensure_local_proxy_ca():
            config.proxy_ca_installed = True
            save_client_config(self._home, config)

    async def _inject_dummy_credentials(self, env: dict[str, str]) -> None:
        connections_data = await self._client.list_connections()
        if isinstance(connections_data, list):
            by_source = await self._client.list_providers_by_source()
            connections_data = {
                "connections": connections_data,
                "by_source": {
                    source: [provider.model_dump(mode="json") for provider in providers]
                    for source, providers in by_source.items()
                },
            }
        connected_names = {entry["name"] for entry in connections_data["connections"]}
        from authsome.auth.models.provider import ProviderDefinition

        for source_providers in connections_data["by_source"].values():
            for provider_dict in source_providers:
                provider = ProviderDefinition.model_validate(provider_dict)
                if provider.name not in connected_names:
                    continue
                if not provider.export:
                    continue
                if provider.export.env:
                    for env_var in provider.export.env.values():
                        env[env_var] = "authsome-proxy-managed"
                        logger.debug("Set dummy env var {} for provider {}", env_var, provider.name)
                if provider.export.model_extra:
                    for env_var in provider.export.model_extra:
                        env[env_var] = "authsome-proxy-managed"
                        logger.debug("Set dummy env var {} for provider {}", env_var, provider.name)

    @staticmethod
    def _build_ca_bundle(server: RunningProxy) -> Path | None:
        """Create a temp file containing system CAs plus the mitmproxy CA cert."""
        mitm_ca = server.ca_cert_path
        if not mitm_ca.exists():
            logger.warning("Mitmproxy CA cert not found at {}; HTTPS may fail", mitm_ca)
            return None

        import certifi

        system_ca_path = Path(certifi.where())

        fd, name = tempfile.mkstemp(prefix="authsome-ca-", suffix=".pem", text=True)
        os.close(fd)
        path = Path(name)
        try:
            content = system_ca_path.read_text(encoding="utf-8") + "\n" + mitm_ca.read_text(encoding="utf-8")
            path.write_text(content, encoding="utf-8")
        except Exception as exc:
            logger.error("Failed to create combined CA bundle: {}", exc)
            with suppress(Exception):
                path.unlink(missing_ok=True)
            return None

        return path

    @staticmethod
    def _merge_no_proxy(existing: str) -> str:
        entries = [item.strip() for item in existing.split(",") if item.strip()]
        for host in ["127.0.0.1", "localhost", "::1"]:
            if host not in entries:
                entries.append(host)
        return ",".join(entries)
