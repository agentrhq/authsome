"""Tests for the HTTP proxy injection feature."""

from __future__ import annotations

from pathlib import Path
from unittest import mock
from unittest.mock import Mock, patch

import pytest

from authsome.auth import AuthService as AuthLayer
from authsome.auth.models.connection import ConnectionRecord
from authsome.auth.models.enums import AuthType, ConnectionStatus
from authsome.proxy.router import RouteMatch, RouteResolution
from authsome.proxy.server import AuthProxyAddon, ProxyRouter, _build_proxy_options, _route
from authsome.server.dependencies import create_auth_service


async def _make_auth(tmp_path: Path) -> AuthLayer:
    home = tmp_path / ".authsome"
    return await create_auth_service(home, identity="steady-wisely-boldly-0042")


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
    async def test_host_url_path_limits_routing(self) -> None:
        auth = mock.AsyncMock()
        provider = mock.Mock()
        provider.oauth = None
        provider.resolve_urls.return_value = provider
        auth.get_provider.side_effect = lambda name: {
            "name": name,
            "display_name": name.title(),
            "auth_type": "api_key",
            "flow": "api_key",
            "host_url": "api.example.com",
        }
        auth.list_connections.return_value = {
            "connections": [
                {
                    "name": "custom",
                    "connections": [
                        {
                            "connection_name": "default",
                            "host_url": "https://api.example.com/v1",
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
    async def test_more_specific_host_url_path_wins_over_host_only_route(self) -> None:
        auth = mock.AsyncMock()
        provider = mock.Mock()
        provider.oauth = None
        provider.resolve_urls.return_value = provider
        auth.get_provider.side_effect = lambda name: {
            "name": name,
            "display_name": name.title(),
            "auth_type": "api_key",
            "flow": "api_key",
            "host_url": "api.example.com",
        }
        auth.list_connections.return_value = {
            "connections": [
                {
                    "name": "root",
                    "connections": [
                        {
                            "connection_name": "default",
                            "host_url": "api.example.com",
                            "base_url": None,
                        }
                    ],
                },
                {
                    "name": "v1",
                    "connections": [
                        {
                            "connection_name": "default",
                            "host_url": "https://api.example.com/v1",
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
    async def test_more_specific_nested_host_url_path_wins(self) -> None:
        auth = mock.AsyncMock()
        provider = mock.Mock()
        provider.oauth = None
        provider.resolve_urls.return_value = provider
        auth.get_provider.side_effect = lambda name: {
            "name": name,
            "display_name": name.title(),
            "auth_type": "api_key",
            "flow": "api_key",
            "host_url": "api.example.com",
        }
        auth.list_connections.return_value = {
            "connections": [
                {
                    "name": "v1",
                    "connections": [
                        {
                            "connection_name": "default",
                            "host_url": "https://api.example.com/v1",
                            "base_url": None,
                        }
                    ],
                },
                {
                    "name": "beta",
                    "connections": [
                        {
                            "connection_name": "default",
                            "host_url": "https://api.example.com/v1/beta",
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
    async def test_equal_specificity_host_url_paths_remain_ambiguous(self) -> None:
        auth = mock.AsyncMock()
        provider = mock.Mock()
        provider.oauth = None
        provider.resolve_urls.return_value = provider
        auth.get_provider.side_effect = lambda name: {
            "name": name,
            "display_name": name.title(),
            "auth_type": "api_key",
            "flow": "api_key",
            "host_url": "api.example.com",
        }
        auth.list_connections.return_value = {
            "connections": [
                {
                    "name": "first",
                    "connections": [
                        {
                            "connection_name": "default",
                            "host_url": "https://api.example.com/v1",
                            "base_url": None,
                        }
                    ],
                },
                {
                    "name": "second",
                    "connections": [
                        {
                            "connection_name": "default",
                            "host_url": "https://api.example.com/v1",
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
    async def test_regex_host_url_matches_multiple_hosts(self) -> None:
        auth = mock.AsyncMock()
        provider = mock.Mock()
        provider.oauth = None
        provider.resolve_urls.return_value = provider
        auth.get_provider.side_effect = lambda name: {
            "name": name,
            "display_name": name.title(),
            "auth_type": "api_key",
            "flow": "api_key",
            "host_url": "api.example.com",
        }
        auth.list_connections.return_value = {
            "connections": [
                {
                    "name": "github-shards",
                    "connections": [
                        {
                            "connection_name": "default",
                            "host_url": r"regex:^api[0-9]+\.github\.com$",
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
            "host_url": "api.example.com",
        }
        auth.list_connections.return_value = {
            "connections": [
                {
                    "name": "regex",
                    "connections": [
                        {
                            "connection_name": "default",
                            "host_url": r"regex:^api[0-9]+\.github\.com$",
                            "base_url": None,
                        }
                    ],
                },
                {
                    "name": "exact",
                    "connections": [
                        {
                            "connection_name": "default",
                            "host_url": "api1.github.com",
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
    async def test_plain_host_url_does_not_use_regex_matching(self) -> None:
        auth = mock.AsyncMock()
        provider = mock.Mock()
        provider.oauth = None
        provider.resolve_urls.return_value = provider
        auth.get_provider.side_effect = lambda name: {
            "name": name,
            "display_name": name.title(),
            "auth_type": "api_key",
            "flow": "api_key",
            "host_url": "api.example.com",
        }
        auth.list_connections.return_value = {
            "connections": [
                {
                    "name": "plain",
                    "connections": [
                        {
                            "connection_name": "default",
                            "host_url": "api.github.com",
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
                            "host_url": "api.example.com",
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

    def _make_addon(self, auth, match, *, miss_reason=None):
        router = mock.Mock()
        router.resolve.return_value = RouteResolution(match=match, miss_reason=miss_reason)

        # Mock the async factory method
        mock_create = mock.AsyncMock(return_value=router)

        patcher = patch("authsome.proxy.server.ProxyRouter.create", mock_create)
        patcher.start()

        addon = AuthProxyAddon(client=auth)
        return addon, router, patcher

    @pytest.mark.asyncio
    async def test_addon_injects_headers_for_matched_request(self) -> None:
        auth = mock.AsyncMock()
        flow = self._make_flow()
        auth.resolve_credentials.return_value = {"headers": {"Authorization": "Bearer sk-test"}, "expires_at": None}

        with patch("authsome.proxy.server.audit.log") as log_mock:
            addon, _router, patcher = self._make_addon(auth, RouteMatch(provider="openai", connection="default"))
            try:
                await addon.request(flow)
            finally:
                patcher.stop()

        assert flow.request.headers["Authorization"] == "Bearer sk-test"
        log_mock.assert_any_call(
            "proxy_inject",
            provider="openai",
            connection="default",
            host="api.openai.com",
            method="GET",
            path="/v1/responses",
        )

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

        with patch("authsome.proxy.server.audit.log") as log_mock:
            addon, _router, patcher = self._make_addon(auth, None, miss_reason="no_match")
            try:
                await addon.request(flow)
            finally:
                patcher.stop()

        auth.resolve_credentials.assert_not_called()
        log_mock.assert_called_once_with("proxy_miss", host="example.com", reason="no_match")

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
        runner = ProxyRunner(auth)

        with patch("authsome.proxy.runner.subprocess.run") as run_mock:
            run_mock.return_value.returncode = 0
            with patch.object(runner, "_start_proxy", return_value=("http://127.0.0.1:8899", mock.Mock())):
                with patch.object(runner, "_build_ca_bundle", return_value=Path("/tmp/fake-ca.pem")):
                    await runner.run(["python", "-c", "print('ok')"])

        env = run_mock.call_args.kwargs["env"]
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

        runner = ProxyRunner(auth)

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
        runner = ProxyRunner(auth)
        server = mock.Mock()

        with patch("authsome.proxy.runner.subprocess.run", side_effect=RuntimeError("boom")):
            with patch.object(runner, "_start_proxy", return_value=("http://127.0.0.1:8899", server)):
                with patch.object(runner, "_build_ca_bundle", return_value=None):
                    with pytest.raises(RuntimeError, match="boom"):
                        await runner.run(["python", "-c", "print('ok')"])

        server.shutdown.assert_called_once()

    def test_runner_merges_existing_no_proxy(self, tmp_path: Path) -> None:
        from authsome.proxy.runner import ProxyRunner

        result = ProxyRunner._merge_no_proxy("internal.corp.com,10.0.0.1")
        assert "internal.corp.com" in result
        assert "10.0.0.1" in result
        assert "127.0.0.1" in result
        assert "localhost" in result
        assert "::1" in result

    def test_add_ca_to_macos_keychain_skips_on_non_macos(self, tmp_path: Path) -> None:
        from authsome.proxy.runner import ProxyRunner

        cert = tmp_path / "ca.pem"
        cert.write_text("fake-cert")

        with patch("authsome.proxy.runner.sys") as mock_sys:
            mock_sys.platform = "linux"
            added = ProxyRunner._add_ca_to_macos_keychain(cert)

        assert added is False

    def test_add_ca_to_macos_keychain_skips_missing_cert(self, tmp_path: Path) -> None:
        from authsome.proxy.runner import ProxyRunner

        missing = tmp_path / "nonexistent.pem"

        with patch("authsome.proxy.runner.sys") as mock_sys:
            mock_sys.platform = "darwin"
            added = ProxyRunner._add_ca_to_macos_keychain(missing)

        assert added is False

    def _make_fake_keychain(self, tmp_path: Path) -> Path:
        """Create a fake login.keychain-db under the tmp_path home structure."""
        keychain_dir = tmp_path / "Library" / "Keychains"
        keychain_dir.mkdir(parents=True)
        keychain = keychain_dir / "login.keychain-db"
        keychain.touch()
        return keychain

    def test_add_ca_to_macos_keychain_skips_when_already_present(self, tmp_path: Path) -> None:
        from authsome.proxy.runner import ProxyRunner

        cert = tmp_path / "ca.pem"
        cert.write_text("fake-cert")
        self._make_fake_keychain(tmp_path)

        with (
            patch("authsome.proxy.runner.sys") as mock_sys,
            patch("authsome.proxy.runner.Path.home", return_value=tmp_path),
            patch("authsome.proxy.runner.subprocess.run") as run_mock,
        ):
            mock_sys.platform = "darwin"
            # find-certificate returns 0 → cert already present
            run_mock.return_value = Mock(returncode=0)
            added = ProxyRunner._add_ca_to_macos_keychain(cert)

        assert added is False
        # Only the find-certificate check should have run, not add-trusted-cert
        assert run_mock.call_count == 1
        assert "find-certificate" in run_mock.call_args[0][0]

    def test_add_ca_to_macos_keychain_returns_true_on_success(self, tmp_path: Path) -> None:
        from authsome.proxy.runner import ProxyRunner

        cert = tmp_path / "ca.pem"
        cert.write_text("fake-cert")
        self._make_fake_keychain(tmp_path)

        find_result = Mock(returncode=1)  # cert not present
        add_result = Mock(returncode=0)  # add succeeded

        with (
            patch("authsome.proxy.runner.sys") as mock_sys,
            patch("authsome.proxy.runner.Path.home", return_value=tmp_path),
            patch("authsome.proxy.runner.subprocess.run", side_effect=[find_result, add_result]),
        ):
            mock_sys.platform = "darwin"
            added = ProxyRunner._add_ca_to_macos_keychain(cert)

        assert added is True

    def test_add_ca_to_macos_keychain_returns_false_on_failure(self, tmp_path: Path) -> None:
        from authsome.proxy.runner import ProxyRunner

        cert = tmp_path / "ca.pem"
        cert.write_text("fake-cert")
        self._make_fake_keychain(tmp_path)

        find_result = Mock(returncode=1)  # cert not present
        add_result = Mock(returncode=1, stderr="denied", stdout="")  # add failed

        with (
            patch("authsome.proxy.runner.sys") as mock_sys,
            patch("authsome.proxy.runner.Path.home", return_value=tmp_path),
            patch("authsome.proxy.runner.subprocess.run", side_effect=[find_result, add_result]),
        ):
            mock_sys.platform = "darwin"
            added = ProxyRunner._add_ca_to_macos_keychain(cert)

        assert added is False

    def test_remove_ca_from_macos_keychain_skips_on_non_macos(self) -> None:
        from authsome.proxy.runner import ProxyRunner

        with patch("authsome.proxy.runner.sys") as mock_sys, patch("authsome.proxy.runner.subprocess.run") as run_mock:
            mock_sys.platform = "linux"
            ProxyRunner._remove_ca_from_macos_keychain()

        run_mock.assert_not_called()

    def test_remove_ca_from_macos_keychain_calls_delete_certificate(self, tmp_path: Path) -> None:
        from authsome.proxy.runner import ProxyRunner

        self._make_fake_keychain(tmp_path)

        with patch("authsome.proxy.runner.sys") as mock_sys, patch("authsome.proxy.runner.subprocess.run") as run_mock:
            mock_sys.platform = "darwin"
            run_mock.return_value = Mock(returncode=0)
            ProxyRunner._remove_ca_from_macos_keychain()

        run_mock.assert_called_once()
        cmd = run_mock.call_args[0][0]
        assert "delete-certificate" in cmd
        assert "mitmproxy" in cmd

    @pytest.mark.asyncio
    async def test_runner_adds_keychain_cert_on_macos_and_removes_after_run(self, tmp_path: Path) -> None:
        from authsome.proxy.runner import ProxyRunner

        auth = await _make_auth(tmp_path)
        runner = ProxyRunner(auth)
        fake_ca = tmp_path / "fake-ca.pem"
        fake_ca.write_text("fake")

        with (
            patch("authsome.proxy.runner.subprocess.run") as run_mock,
            patch.object(runner, "_start_proxy", return_value=("http://127.0.0.1:8899", Mock())),
            patch.object(runner, "_build_ca_bundle", return_value=fake_ca),
            patch.object(ProxyRunner, "_add_ca_to_macos_keychain", return_value=True) as add_mock,
            patch.object(ProxyRunner, "_remove_ca_from_macos_keychain") as remove_mock,
        ):
            run_mock.return_value = Mock(returncode=0)
            await runner.run(["echo", "hello"])

        add_mock.assert_called_once()
        remove_mock.assert_called_once()


class TestProxyServer:
    """Proxy server options and lifecycle helpers."""

    def test_proxy_options_verify_upstream_tls(self, tmp_path: Path) -> None:
        opts = _build_proxy_options("127.0.0.1", 0, tmp_path)

        assert opts.ssl_insecure is False


# ── Provider metadata tests ─────────────────────────────────────────────


class TestProviderProxyMetadata:
    """Bundled provider definitions include host_url for proxy routing."""

    @pytest.mark.asyncio
    async def test_openai_provider_has_host_url(self, tmp_path: Path) -> None:
        auth = await _make_auth(tmp_path)
        provider = await auth.get_provider("openai")
        assert provider.host_url == "api.openai.com"

    @pytest.mark.asyncio
    async def test_github_provider_has_host_url(self, tmp_path: Path) -> None:
        auth = await _make_auth(tmp_path)
        provider = await auth.get_provider("github")
        assert provider.host_url == "api.github.com"


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
