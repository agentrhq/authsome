"""Tests for the HTTP proxy injection feature."""

from __future__ import annotations

from pathlib import Path
from unittest import mock
from unittest.mock import patch

import pytest

from authsome.auth import AuthService as AuthLayer
from authsome.auth.models.connection import ConnectionRecord
from authsome.auth.models.enums import AuthType, ConnectionStatus
from authsome.proxy.router import RouteMatch, RouteResolution
from authsome.proxy.server import AuthProxyAddon, ProxyRouter, _build_proxy_options, _route
from authsome.server.dependencies import create_auth_service
from authsome.server.urls import DEFAULT_SERVER_BASE_URL


async def _make_auth(tmp_path: Path) -> AuthLayer:
    home = tmp_path / ".authsome"
    return await create_auth_service(home, identity="steady-wisely-boldly-0042", vault_id="steady-wisely-boldly-0042")


async def _save_connection_record(
    auth: AuthLayer,
    provider_name: str,
    api_key: str,
    connection_name: str = "default",
) -> None:
    record = ConnectionRecord(
        provider=provider_name,
        identity=auth._identity,
        connection_name=connection_name,
        auth_type=AuthType.API_KEY,
        status=ConnectionStatus.CONNECTED,
        api_key=api_key,
    )
    await auth._save_connection(record)
    await auth._update_provider_metadata(provider_name, connection_name)


# ── Routing function tests ────────────────────────────────────────────────


class TestRouting:
    """_route() matching and rejection behaviour."""

    @pytest.mark.asyncio
    async def test_matches_provider_host(self, tmp_path: Path) -> None:
        auth = await _make_auth(tmp_path)
        await _save_connection_record(auth, "openai", "sk-test-padded-for-regex-12")

        match = await _route(auth, "https", "api.openai.com", 443, "/v1/responses")

        assert match == RouteMatch(provider="openai", connection="default")

    @pytest.mark.asyncio
    async def test_rejects_plain_http_provider_host(self, tmp_path: Path) -> None:
        auth = await _make_auth(tmp_path)
        await _save_connection_record(auth, "openai", "sk-test-padded-for-regex-12")

        assert await _route(auth, "http", "api.openai.com", 80, "/v1/responses") is None

    @pytest.mark.asyncio
    async def test_ignores_named_connection_without_default(self, tmp_path: Path) -> None:
        auth = await _make_auth(tmp_path)
        await _save_connection_record(auth, "openai", "sk-work-padded-for-regex-12", "work")

        match = await _route(auth, "https", "api.openai.com", 443, "/v1/responses")

        assert match is None

    @pytest.mark.asyncio
    async def test_routes_default_when_named_connection_also_exists(self, tmp_path: Path) -> None:
        auth = await _make_auth(tmp_path)
        await _save_connection_record(auth, "openai", "sk-default-padded-for-regex-12")
        await _save_connection_record(auth, "openai", "sk-work-padded-for-regex-12", "work")

        match = await _route(auth, "https", "api.openai.com", 443, "/v1/responses")

        assert match == RouteMatch(provider="openai", connection="default")

    @pytest.mark.asyncio
    async def test_api_url_path_limits_routing(self) -> None:
        auth = mock.AsyncMock()
        provider = mock.Mock()
        provider.oauth = None
        provider.resolve_urls.return_value = provider
        auth.get_provider.side_effect = lambda name: {
            "name": name,
            "display_name": name.title(),
            "auth_type": "api_key",
            "flow": "api_key",
            "api_url": "api.example.com",
        }
        auth.list_connections.return_value = {
            "connections": [
                {
                    "name": "custom",
                    "connections": [
                        {
                            "connection_name": "default",
                            "api_url": "https://api.example.com/v1",
                            "base_url": None,
                        }
                    ],
                }
            ]
        }

        router = await ProxyRouter.create(auth)

        assert router.route("https", "api.example.com", 443, "/v1/resources") == RouteMatch(
            provider="custom",
            connection="default",
        )
        assert router.route("https", "api.example.com", 443, "/v2/resources") is None

    @pytest.mark.asyncio
    async def test_more_specific_api_url_path_wins_over_host_only_route(self) -> None:
        auth = mock.AsyncMock()
        provider = mock.Mock()
        provider.oauth = None
        provider.resolve_urls.return_value = provider
        auth.get_provider.side_effect = lambda name: {
            "name": name,
            "display_name": name.title(),
            "auth_type": "api_key",
            "flow": "api_key",
            "api_url": "api.example.com",
        }
        auth.list_connections.return_value = {
            "connections": [
                {
                    "name": "root",
                    "connections": [
                        {
                            "connection_name": "default",
                            "api_url": "api.example.com",
                            "base_url": None,
                        }
                    ],
                },
                {
                    "name": "v1",
                    "connections": [
                        {
                            "connection_name": "default",
                            "api_url": "https://api.example.com/v1",
                            "base_url": None,
                        }
                    ],
                },
            ]
        }

        router = await ProxyRouter.create(auth)

        assert router.route("https", "api.example.com", 443, "/v1/resources") == RouteMatch(
            provider="v1",
            connection="default",
        )
        assert router.route("https", "api.example.com", 443, "/v2/resources") == RouteMatch(
            provider="root",
            connection="default",
        )

    @pytest.mark.asyncio
    async def test_more_specific_nested_api_url_path_wins(self) -> None:
        auth = mock.AsyncMock()
        provider = mock.Mock()
        provider.oauth = None
        provider.resolve_urls.return_value = provider
        auth.get_provider.side_effect = lambda name: {
            "name": name,
            "display_name": name.title(),
            "auth_type": "api_key",
            "flow": "api_key",
            "api_url": "api.example.com",
        }
        auth.list_connections.return_value = {
            "connections": [
                {
                    "name": "v1",
                    "connections": [
                        {
                            "connection_name": "default",
                            "api_url": "https://api.example.com/v1",
                            "base_url": None,
                        }
                    ],
                },
                {
                    "name": "beta",
                    "connections": [
                        {
                            "connection_name": "default",
                            "api_url": "https://api.example.com/v1/beta",
                            "base_url": None,
                        }
                    ],
                },
            ]
        }

        router = await ProxyRouter.create(auth)

        assert router.route("https", "api.example.com", 443, "/v1/beta/resources") == RouteMatch(
            provider="beta",
            connection="default",
        )
        assert router.route("https", "api.example.com", 443, "/v1/resources") == RouteMatch(
            provider="v1",
            connection="default",
        )

    @pytest.mark.asyncio
    async def test_equal_specificity_api_url_paths_remain_ambiguous(self) -> None:
        auth = mock.AsyncMock()
        provider = mock.Mock()
        provider.oauth = None
        provider.resolve_urls.return_value = provider
        auth.get_provider.side_effect = lambda name: {
            "name": name,
            "display_name": name.title(),
            "auth_type": "api_key",
            "flow": "api_key",
            "api_url": "api.example.com",
        }
        auth.list_connections.return_value = {
            "connections": [
                {
                    "name": "first",
                    "connections": [
                        {
                            "connection_name": "default",
                            "api_url": "https://api.example.com/v1",
                            "base_url": None,
                        }
                    ],
                },
                {
                    "name": "second",
                    "connections": [
                        {
                            "connection_name": "default",
                            "api_url": "https://api.example.com/v1",
                            "base_url": None,
                        }
                    ],
                },
            ]
        }

        router = await ProxyRouter.create(auth)

        assert router.route("https", "api.example.com", 443, "/v1/resources") is None
        amb = router.resolve("https", "api.example.com", 443, "/v1/resources")
        assert amb.match is None and amb.miss_reason == "ambiguous"

    @pytest.mark.asyncio
    async def test_regex_api_url_matches_multiple_hosts(self) -> None:
        auth = mock.AsyncMock()
        provider = mock.Mock()
        provider.oauth = None
        provider.resolve_urls.return_value = provider
        auth.get_provider.side_effect = lambda name: {
            "name": name,
            "display_name": name.title(),
            "auth_type": "api_key",
            "flow": "api_key",
            "api_url": "api.example.com",
        }
        auth.list_connections.return_value = {
            "connections": [
                {
                    "name": "github-shards",
                    "connections": [
                        {
                            "connection_name": "default",
                            "api_url": r"regex:^api[0-9]+\.github\.com$",
                            "base_url": None,
                        }
                    ],
                }
            ]
        }

        router = await ProxyRouter.create(auth)

        assert router.route("https", "api1.github.com", 443, "/repos") == RouteMatch(
            provider="github-shards",
            connection="default",
        )
        assert router.route("https", "api2.github.com", 443, "/repos") == RouteMatch(
            provider="github-shards",
            connection="default",
        )
        assert router.route("https", "api.github.com", 443, "/repos") is None

    @pytest.mark.asyncio
    async def test_exact_host_route_wins_over_regex_route(self) -> None:
        auth = mock.AsyncMock()
        provider = mock.Mock()
        provider.oauth = None
        provider.resolve_urls.return_value = provider
        auth.get_provider.side_effect = lambda name: {
            "name": name,
            "display_name": name.title(),
            "auth_type": "api_key",
            "flow": "api_key",
            "api_url": "api.example.com",
        }
        auth.list_connections.return_value = {
            "connections": [
                {
                    "name": "regex",
                    "connections": [
                        {
                            "connection_name": "default",
                            "api_url": r"regex:^api[0-9]+\.github\.com$",
                            "base_url": None,
                        }
                    ],
                },
                {
                    "name": "exact",
                    "connections": [
                        {
                            "connection_name": "default",
                            "api_url": "api1.github.com",
                            "base_url": None,
                        }
                    ],
                },
            ]
        }

        router = await ProxyRouter.create(auth)

        assert router.route("https", "api1.github.com", 443, "/repos") == RouteMatch(
            provider="exact",
            connection="default",
        )
        assert router.route("https", "api2.github.com", 443, "/repos") == RouteMatch(
            provider="regex",
            connection="default",
        )

    @pytest.mark.asyncio
    async def test_plain_api_url_does_not_use_regex_matching(self) -> None:
        auth = mock.AsyncMock()
        provider = mock.Mock()
        provider.oauth = None
        provider.resolve_urls.return_value = provider
        auth.get_provider.side_effect = lambda name: {
            "name": name,
            "display_name": name.title(),
            "auth_type": "api_key",
            "flow": "api_key",
            "api_url": "api.example.com",
        }
        auth.list_connections.return_value = {
            "connections": [
                {
                    "name": "plain",
                    "connections": [
                        {
                            "connection_name": "default",
                            "api_url": "api.github.com",
                            "base_url": None,
                        }
                    ],
                }
            ]
        }

        router = await ProxyRouter.create(auth)

        assert router.route("https", "api.github.com", 443, "/repos") == RouteMatch(
            provider="plain",
            connection="default",
        )
        assert router.route("https", "apiXgithub.com", 443, "/repos") is None

    @pytest.mark.asyncio
    async def test_rejects_loopback_host(self, tmp_path: Path) -> None:
        auth = await _make_auth(tmp_path)

        assert await _route(auth, "http", "127.0.0.1", 8080, "/anything") is None
        assert await _route(auth, "http", "localhost", 8080, "/anything") is None
        assert await _route(auth, "http", "::1", 8080, "/anything") is None

    @pytest.mark.asyncio
    async def test_rejects_provider_token_endpoint(self, tmp_path: Path) -> None:
        auth = await _make_auth(tmp_path)

        assert await _route(auth, "https", "github.com", 443, "/login/oauth/access_token") is None

    @pytest.mark.asyncio
    async def test_rejects_connected_provider_auth_endpoint_with_query(self) -> None:
        auth = mock.AsyncMock()
        auth.get_provider.return_value = {
            "name": "custom",
            "display_name": "Custom",
            "auth_type": "oauth2",
            "flow": "pkce",
            "oauth": {
                "authorization_url": "https://api.example.com/oauth/authorize",
                "token_url": "https://api.example.com/oauth/token",
            },
        }
        auth.list_connections.return_value = {
            "connections": [
                {
                    "name": "custom",
                    "connections": [
                        {
                            "connection_name": "default",
                            "api_url": "api.example.com",
                            "base_url": None,
                        }
                    ],
                }
            ]
        }

        router = await ProxyRouter.create(auth)

        assert router.route("https", "api.example.com", 443, "/oauth/token?grant_type=refresh_token") is None

    @pytest.mark.asyncio
    async def test_no_match_for_unknown_host(self, tmp_path: Path) -> None:
        auth = await _make_auth(tmp_path)

        assert await _route(auth, "https", "unknown.example.com", 443, "/v1") is None
        router = await ProxyRouter.create(auth)
        miss = router.resolve("https", "unknown.example.com", 443, "/v1")
        assert miss.match is None and miss.miss_reason == "no_match"

    @pytest.mark.asyncio
    async def test_no_match_without_connection(self, tmp_path: Path) -> None:
        auth = await _make_auth(tmp_path)

        assert await _route(auth, "https", "api.openai.com", 443, "/v1/responses") is None


# ── Addon tests ──────────────────────────────────────────────────────────


class TestAuthProxyAddon:
    """AuthProxyAddon header injection and passthrough."""

    def _make_flow(self, scheme="https", host="api.openai.com", port=443, path="/v1/responses", headers=None):
        flow = mock.Mock()
        flow.request.scheme = scheme
        flow.request.host = host
        flow.request.port = port
        flow.request.path = path
        flow.request.method = "GET"
        flow.request.headers = headers if headers is not None else {}
        return flow

    def _make_addon(self, auth, match, *, miss_reason=None, mode="connected_allow"):
        router = mock.Mock()
        router.resolve.return_value = RouteResolution(match=match, miss_reason=miss_reason)

        mock_create = mock.AsyncMock(return_value=router)

        patcher = patch("authsome.proxy.server.ProxyRouter.create", mock_create)
        patcher.start()

        addon = AuthProxyAddon(client=auth, mode=mode)
        return addon, router, patcher

    @pytest.mark.asyncio
    async def test_addon_injects_headers_for_matched_request(self) -> None:
        auth = mock.AsyncMock()
        flow = self._make_flow()
        auth.resolve_credentials.return_value = {"headers": {"Authorization": "Bearer sk-test"}, "expires_at": None}

        addon, _router, patcher = self._make_addon(auth, RouteMatch(provider="openai", connection="default"))
        try:
            await addon.request(flow)
        finally:
            patcher.stop()

        assert flow.request.headers["Authorization"] == "Bearer sk-test"

    @pytest.mark.asyncio
    async def test_addon_overwrites_existing_authorization_header(self) -> None:
        auth = mock.AsyncMock()
        flow = self._make_flow(headers={"Authorization": "Bearer existing"})
        auth.resolve_credentials.return_value = {"headers": {"Authorization": "Bearer sk-authsome"}, "expires_at": None}

        addon, _router, patcher = self._make_addon(auth, RouteMatch(provider="openai", connection="default"))
        try:
            await addon.request(flow)
        finally:
            patcher.stop()

        assert flow.request.headers["Authorization"] == "Bearer sk-authsome"

    @pytest.mark.asyncio
    async def test_addon_skips_unmatched_request(self) -> None:
        auth = mock.AsyncMock()
        flow = self._make_flow(host="example.com", path="/")

        addon, _router, patcher = self._make_addon(auth, None, miss_reason="no_match")
        try:
            await addon.request(flow)
        finally:
            patcher.stop()

        auth.resolve_credentials.assert_not_called()

    @pytest.mark.asyncio
    async def test_addon_denies_no_match_with_generic_body_in_connected_deny(self) -> None:
        auth = mock.AsyncMock()
        flow = self._make_flow(host="example.com", path="/")

        with patch("authsome.proxy.server.audit.log") as log_mock:
            addon, _router, patcher = self._make_addon(auth, None, miss_reason="no_match", mode="connected_deny")
            try:
                await addon.request(flow)
            finally:
                patcher.stop()

        assert flow.response.status_code == 403
        assert flow.response.content == b"Forbidden by Authsome proxy policy"
        log_mock.assert_called_once_with("proxy_deny", host="example.com", reason="no_match")
        auth.resolve_credentials.assert_not_called()

    @pytest.mark.asyncio
    async def test_addon_denies_no_credentials_with_provider_hint_in_configured_deny(self) -> None:
        auth = mock.AsyncMock()
        auth.resolve_credentials.side_effect = RuntimeError("no connection for openai")
        flow = self._make_flow()

        with patch("authsome.proxy.server.audit.log") as log_mock:
            addon, _router, patcher = self._make_addon(
                auth,
                RouteMatch(provider="openai", connection="default"),
                mode="configured_deny",
            )
            try:
                await addon.request(flow)
            finally:
                patcher.stop()

        assert flow.response.status_code == 403
        body = flow.response.content.decode("utf-8")
        assert "openai" in body
        assert "authsome login openai" in body
        assert f"{DEFAULT_SERVER_BASE_URL}/ui/apps/openai" in body
        log_mock.assert_any_call(
            "proxy_no_credentials",
            host="api.openai.com",
            provider="openai",
            connection="default",
        )
        log_mock.assert_any_call("proxy_deny", host="api.openai.com", reason="no_credentials")

    @pytest.mark.asyncio
    async def test_addon_kills_connect_tunnel_on_deny(self) -> None:
        auth = mock.AsyncMock()
        flow = self._make_flow(host="example.com", path="/")
        flow.request.method = "CONNECT"

        with patch("authsome.proxy.server.audit.log"):
            addon, _router, patcher = self._make_addon(auth, None, miss_reason="no_match", mode="connected_deny")
            try:
                await addon.request(flow)
            finally:
                patcher.stop()

        flow.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_addon_continues_on_header_retrieval_failure(self) -> None:
        auth = mock.AsyncMock()
        auth.resolve_credentials.side_effect = RuntimeError("token expired")
        flow = self._make_flow()

        addon, _router, patcher = self._make_addon(auth, RouteMatch(provider="openai", connection="default"))
        try:
            await addon.request(flow)
        finally:
            patcher.stop()

        assert "Authorization" not in flow.request.headers

    @pytest.mark.asyncio
    async def test_addon_caches_headers_for_connection(self) -> None:
        auth = mock.AsyncMock()
        auth.resolve_credentials.return_value = {"headers": {"Authorization": "Bearer sk-test"}, "expires_at": None}
        addon, _router, patcher = self._make_addon(auth, RouteMatch(provider="openai", connection="default"))
        try:
            await addon.request(self._make_flow())
            await addon.request(self._make_flow())
        finally:
            patcher.stop()

        auth.resolve_credentials.assert_called_once_with(provider="openai", connection="default")


# ── Runner tests ─────────────────────────────────────────────────────────


class TestProxyRunner:
    """ProxyRunner subprocess environment and lifecycle."""

    @pytest.mark.asyncio
    async def test_runner_sets_proxy_environment(self, tmp_path: Path) -> None:
        from authsome.proxy.runner import ProxyRunner

        auth = await _make_auth(tmp_path)
        runner = ProxyRunner(auth, home=tmp_path)

        with patch("authsome.proxy.runner.subprocess.run") as run_mock:
            run_mock.return_value.returncode = 0
            with patch("authsome.proxy.runner.ensure_local_proxy_ca") as ensure_ca_mock:
                with patch.object(runner, "_start_proxy", return_value=("http://127.0.0.1:8899", mock.Mock())):
                    with patch.object(runner, "_build_ca_bundle", return_value=Path("/tmp/fake-ca.pem")):
                        await runner.run(["python", "-c", "print('ok')"])

        env = run_mock.call_args.kwargs["env"]
        ensure_ca_mock.assert_not_called()
        assert env["HTTP_PROXY"] == "http://127.0.0.1:8899"
        assert env["HTTPS_PROXY"] == "http://127.0.0.1:8899"
        assert env["http_proxy"] == "http://127.0.0.1:8899"
        assert env["https_proxy"] == "http://127.0.0.1:8899"
        assert env["SSL_CERT_FILE"] == "/tmp/fake-ca.pem"
        assert "localhost" in env["NO_PROXY"]
        assert "127.0.0.1" in env["NO_PROXY"]
        assert "::1" in env["NO_PROXY"]
        assert env.get("OPENAI_API_KEY") != "authsome-proxy-managed"

    @pytest.mark.asyncio
    async def test_runner_injects_dummy_credentials_for_connected_providers(self, tmp_path: Path) -> None:
        from authsome.proxy.runner import ProxyRunner

        auth = await _make_auth(tmp_path)
        await _save_connection_record(auth, "openai", "sk-real-padded-for-regex-12")

        runner = ProxyRunner(auth, home=tmp_path)

        with patch("authsome.proxy.runner.subprocess.run") as run_mock:
            run_mock.return_value.returncode = 0
            with patch.object(runner, "_start_proxy", return_value=("http://127.0.0.1:8899", mock.Mock())):
                with patch.object(runner, "_build_ca_bundle", return_value=None):
                    await runner.run(["python", "-c", "print('ok')"])

        env = run_mock.call_args.kwargs["env"]
        assert env["OPENAI_API_KEY"] == "authsome-proxy-managed"
        assert "sk-real" not in env.values()

    @pytest.mark.asyncio
    async def test_runner_stops_proxy_on_subprocess_failure(self, tmp_path: Path) -> None:
        from authsome.proxy.runner import ProxyRunner

        auth = await _make_auth(tmp_path)
        runner = ProxyRunner(auth, home=tmp_path)
        server = mock.Mock()

        with patch("authsome.proxy.runner.subprocess.run", side_effect=RuntimeError("boom")):
            with patch.object(runner, "_start_proxy", return_value=("http://127.0.0.1:8899", server)):
                with patch.object(runner, "_build_ca_bundle", return_value=None):
                    with pytest.raises(RuntimeError, match="boom"):
                        await runner.run(["python", "-c", "print('ok')"])

        server.shutdown.assert_called_once()

    def test_start_proxy_ensures_local_proxy_ca_once(self, tmp_path: Path) -> None:
        from authsome.proxy.runner import ProxyRunner

        runner = ProxyRunner(mock.Mock(), home=tmp_path)
        server = mock.Mock(url="http://127.0.0.1:8899")

        with patch("authsome.proxy.runner.ensure_local_proxy_ca") as ensure_ca_mock:
            with patch("authsome.proxy.runner.start_proxy_server", return_value=server) as start_mock:
                proxy_url, returned_server = runner._start_proxy()

        ensure_ca_mock.assert_called_once_with(tmp_path)
        start_mock.assert_called_once_with(runner._client, mode="connected_allow")
        assert proxy_url == "http://127.0.0.1:8899"
        assert returned_server is server

    def test_start_proxy_passes_client_config_mode(self, tmp_path: Path) -> None:
        from authsome.cli.client_config import ClientConfig, save_client_config
        from authsome.proxy.runner import ProxyRunner

        save_client_config(tmp_path, ClientConfig(proxy_mode="configured_deny"))
        runner = ProxyRunner(mock.Mock(), home=tmp_path)
        server = mock.Mock(url="http://127.0.0.1:8899")

        with patch("authsome.proxy.runner.ensure_local_proxy_ca"):
            with patch("authsome.proxy.runner.start_proxy_server", return_value=server) as start_mock:
                runner._start_proxy()

        start_mock.assert_called_once_with(runner._client, mode="configured_deny")

    def test_ensure_local_proxy_ca_sets_flag_after_success(self, tmp_path: Path) -> None:
        from authsome.cli.client_config import load_client_config
        from authsome.proxy.certs import ensure_local_proxy_ca

        with patch("authsome.proxy.certs._ensure_macos_keychain_ca", return_value=True) as ensure_ca_mock:
            ensure_local_proxy_ca(tmp_path)

        ensure_ca_mock.assert_called_once_with()
        assert load_client_config(tmp_path).proxy_ca_installed is True

    def test_ensure_local_proxy_ca_skips_repeat_prompt_once_flagged(self, tmp_path: Path) -> None:
        from authsome.cli.client_config import ClientConfig, save_client_config
        from authsome.proxy.certs import ensure_local_proxy_ca

        save_client_config(tmp_path, ClientConfig(proxy_ca_installed=True))

        with patch("authsome.proxy.certs._ensure_macos_keychain_ca") as ensure_ca_mock:
            ensure_local_proxy_ca(tmp_path)

        ensure_ca_mock.assert_not_called()

    def test_runner_merges_existing_no_proxy(self, tmp_path: Path) -> None:
        from authsome.proxy.runner import ProxyRunner

        result = ProxyRunner._merge_no_proxy("internal.corp.com,10.0.0.1")
        assert "internal.corp.com" in result
        assert "10.0.0.1" in result
        assert "127.0.0.1" in result
        assert "localhost" in result
        assert "::1" in result


class TestProxyServer:
    """Proxy server options and lifecycle helpers."""

    def test_proxy_options_verify_upstream_tls(self, tmp_path: Path) -> None:
        opts = _build_proxy_options("127.0.0.1", 0, tmp_path)

        assert opts.ssl_insecure is False


# ── Provider metadata tests ─────────────────────────────────────────────


class TestProviderProxyMetadata:
    """Bundled provider definitions include api_url for proxy routing."""

    @pytest.mark.asyncio
    async def test_openai_provider_has_api_url(self, tmp_path: Path) -> None:
        auth = await _make_auth(tmp_path)
        provider = await auth.get_provider("openai")
        assert provider.api_url == "api.openai.com"

    @pytest.mark.asyncio
    async def test_github_provider_has_api_url(self, tmp_path: Path) -> None:
        auth = await _make_auth(tmp_path)
        provider = await auth.get_provider("github")
        assert provider.api_url == "api.github.com"


# ── CLI tests ────────────────────────────────────────────────────────────


class TestProxyCLI:
    """CLI integration for ``authsome run``."""

    def test_run_requires_command(self) -> None:
        from click.testing import CliRunner

        from authsome.cli.main import cli

        with patch("authsome.cli.context.resolve_runtime_client", new_callable=mock.AsyncMock) as mock_resolve:
            mock_resolve.return_value = mock.AsyncMock()
            runner = CliRunner()
            result = runner.invoke(cli, ["run"])

        assert result.exit_code != 0

    def test_run_invokes_runner(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from authsome.cli.main import cli

        with patch("authsome.cli.context.resolve_runtime_client", new_callable=mock.AsyncMock) as mock_resolve:
            mock_resolve.return_value = mock.AsyncMock()
            with patch("authsome.proxy.runner.ProxyRunner.run", new_callable=mock.AsyncMock) as run_mock:
                run_mock.return_value = mock.Mock(returncode=0)

                with patch("authsome.proxy.runner.ProxyRunner.__init__", return_value=None):
                    runner = CliRunner()
                    _result = runner.invoke(cli, ["run", "--", "echo", "hello"])

        run_mock.assert_called_once()


# ── Documentation tests ──────────────────────────────────────────────────


class TestDocumentation:
    """Verify that docs mention the proxy run command."""

    def test_readme_mentions_run_command(self) -> None:
        readme = Path("README.md").read_text(encoding="utf-8")
        assert "authsome run" in readme
