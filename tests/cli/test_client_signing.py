import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi import status

from authsome.cli.client import AuthsomeApiClient
from authsome.cli.config import ClientConfig
from authsome.cli.identity import RuntimeIdentity


def _patch_httpx_request(monkeypatch, handler) -> None:
    class FakeAsyncClient:
        def __init__(self, timeout=None):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, method, url, content=None, headers=None):
            return handler(method, url, data=content, headers=headers, timeout=self.timeout)

    monkeypatch.setattr("authsome.cli.client.httpx.AsyncClient", FakeAsyncClient)


@pytest.mark.asyncio
async def test_protected_request_sends_pop_header(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    captured: dict = {}

    def fake_request(method, url, data=None, headers=None, timeout=None):
        captured.update({"method": method, "url": url, "data": data, "headers": headers, "timeout": timeout})
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"connections": [], "by_source": {"bundled": [], "custom": []}}
        return response

    _patch_httpx_request(monkeypatch, fake_request)

    await AuthsomeApiClient("http://127.0.0.1:7998").list_connections()

    assert captured["headers"]["Authorization"].startswith("PoP ")


@pytest.mark.asyncio
async def test_health_request_is_unsigned(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    captured: dict = {}

    def fake_request(method, url, data=None, headers=None, timeout=None):
        captured.update({"method": method, "url": url, "data": data, "headers": headers, "timeout": timeout})
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"status": "ok", "version": "0.0.0"}
        return response

    _patch_httpx_request(monkeypatch, fake_request)

    await AuthsomeApiClient("http://127.0.0.1:7998").health()

    assert "Authorization" not in captured["headers"]


@pytest.mark.asyncio
async def test_post_body_is_signed_as_sent(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    captured: dict = {}

    def fake_request(method, url, data=None, headers=None, timeout=None):
        captured.update({"method": method, "url": url, "data": data, "headers": headers, "timeout": timeout})
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"status": "ok"}
        return response

    _patch_httpx_request(monkeypatch, fake_request)

    await AuthsomeApiClient("http://127.0.0.1:7998").set_default_connection("github", "work")

    assert captured["data"] == json.dumps({}, separators=(",", ":"), sort_keys=True).encode("utf-8")


@pytest.mark.asyncio
async def test_set_global_connection_request_is_signed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    captured: dict = {}

    def fake_request(method, url, data=None, headers=None, timeout=None):
        captured.update({"method": method, "url": url, "data": data, "headers": headers, "timeout": timeout})
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"status": "ok", "provider": "github", "connection_name": "work"}
        return response

    _patch_httpx_request(monkeypatch, fake_request)

    await AuthsomeApiClient("http://127.0.0.1:7998").set_global_connection("github", "work")

    assert captured["method"] == "POST"
    assert captured["url"].endswith("/api/connections/github/work/global")
    assert captured["headers"]["Authorization"].startswith("PoP ")


@pytest.mark.asyncio
async def test_unset_global_connection_request_is_signed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    captured: dict = {}

    def fake_request(method, url, data=None, headers=None, timeout=None):
        captured.update({"method": method, "url": url, "data": data, "headers": headers, "timeout": timeout})
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"status": "ok", "provider": "github", "deleted": True}
        return response

    _patch_httpx_request(monkeypatch, fake_request)

    await AuthsomeApiClient("http://127.0.0.1:7998").unset_global_connection("github")

    assert captured["method"] == "DELETE"
    assert captured["url"].endswith("/api/connections/github/global")
    assert captured["headers"]["Authorization"].startswith("PoP ")


@pytest.mark.asyncio
async def test_proxy_routes_request_is_signed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    captured: dict = {}

    def fake_request(method, url, data=None, headers=None, timeout=None):
        captured.update({"method": method, "url": url, "data": data, "headers": headers, "timeout": timeout})
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"routes": []}
        return response

    _patch_httpx_request(monkeypatch, fake_request)

    await AuthsomeApiClient("http://127.0.0.1:7998").proxy_routes()

    assert captured["method"] == "GET"
    assert "/proxy/routes" in captured["url"]
    assert captured["url"].endswith("scope=connected")
    assert captured["headers"]["Authorization"].startswith("PoP ")


@pytest.mark.asyncio
async def test_resolve_credentials_request_is_signed(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    captured: dict = {}

    def fake_request(method, url, data=None, headers=None, timeout=None):
        captured.update({"method": method, "url": url, "data": data, "headers": headers, "timeout": timeout})
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "provider": "github",
            "connection": "default",
            "headers": {"Authorization": "Bearer ghu_test"},
            "expires_at": None,
        }
        return response

    _patch_httpx_request(monkeypatch, fake_request)

    await AuthsomeApiClient("http://127.0.0.1:7998").resolve_credentials(provider="github", connection="default")

    assert captured["method"] == "POST"
    assert captured["url"].endswith("/credentials/resolve")
    assert captured["headers"]["Authorization"].startswith("PoP ")


@pytest.mark.asyncio
async def test_registered_identity_skips_reregister_roundtrip(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    base_url = "http://127.0.0.1:7998"
    identity = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")
    ClientConfig(active_identity=identity.handle).save(tmp_path)
    calls: list[tuple[str, str]] = []

    def fake_request(method, url, data=None, headers=None, timeout=None):
        calls.append((method, url))
        response = Mock()
        response.raise_for_status.return_value = None
        if f"/api/identities/{identity.handle}" in url:
            response.json.return_value = {"identity": identity.handle, "registration_status": "claimed"}
        else:
            response.json.return_value = {"connections": [], "by_source": {"bundled": [], "custom": []}}
        return response

    _patch_httpx_request(monkeypatch, fake_request)

    await AuthsomeApiClient(base_url).list_connections()

    assert calls == [
        ("GET", f"http://127.0.0.1:7998/api/identities/{identity.handle}"),
        ("GET", "http://127.0.0.1:7998/api/connections"),
    ]


@pytest.mark.asyncio
async def test_unregistered_identity_registers_on_first_use(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    server = "http://127.0.0.1:7998"
    identity = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")
    ClientConfig(active_identity=identity.handle).save(tmp_path)
    calls: list[tuple[str, str]] = []

    def fake_request(method, url, data=None, headers=None, timeout=None):
        calls.append((method, url))
        response = Mock()
        if f"/api/identities/{identity.handle}" in url and method == "GET":
            response.status_code = status.HTTP_404_NOT_FOUND
            response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Not Found", request=Mock(), response=Mock(status_code=status.HTTP_404_NOT_FOUND)
            )
        else:
            response.status_code = status.HTTP_200_OK
            response.raise_for_status.return_value = None
            if url.endswith("/api/identities/register"):
                response.json.return_value = {
                    "identity": identity.handle,
                    "did": identity.did,
                    "registration_status": "claimed",
                }
            else:
                response.json.return_value = {"connections": [], "by_source": {"bundled": [], "custom": []}}
        return response

    _patch_httpx_request(monkeypatch, fake_request)

    await AuthsomeApiClient(server).list_connections()

    assert calls == [
        ("GET", f"http://127.0.0.1:7998/api/identities/{identity.handle}"),
        ("POST", "http://127.0.0.1:7998/api/identities/register"),
        ("GET", "http://127.0.0.1:7998/api/connections"),
    ]


@pytest.mark.asyncio
async def test_bootstrapped_identity_is_saved_as_active_agent(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    captured: dict = {}

    def fake_request(method, url, data=None, headers=None, timeout=None):
        captured.update({"method": method, "url": url, "data": data, "headers": headers, "timeout": timeout})
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"connections": [], "by_source": {"bundled": [], "custom": []}}
        return response

    _patch_httpx_request(monkeypatch, fake_request)

    await AuthsomeApiClient("http://127.0.0.1:7998").list_connections()

    config = ClientConfig.load(tmp_path)
    assert config.active_identity is not None


@pytest.mark.asyncio
async def test_identity_env_override_wins_over_active_identity(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.setenv("AUTHSOME_IDENTITY", "rapid-brightly-firmly-0007")
    base_url = "http://127.0.0.1:7998"
    RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")
    override_identity = RuntimeIdentity.create(tmp_path, "rapid-brightly-firmly-0007")
    ClientConfig(active_identity="steady-wisely-boldly-0042").save(tmp_path)

    client = AuthsomeApiClient(base_url)
    client.get_identity_status = AsyncMock(  # type: ignore[method-assign]
        return_value={"identity": override_identity.handle, "registration_status": "claimed"}
    )
    identity = await client.ensure_identity_ready()

    assert identity.handle == "rapid-brightly-firmly-0007"


@pytest.mark.asyncio
async def test_env_identity_protected_request_signs_without_identity_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    source_identity = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")
    private_key_hex = RuntimeIdentity.key_path(tmp_path, source_identity.handle).read_text(encoding="utf-8").strip()
    monkeypatch.setenv("AUTHSOME_IDENTITY", "rapid-brightly-firmly-0007")
    monkeypatch.setenv("AUTHSOME_IDENTITY_PRIVATE_KEY", private_key_hex)
    captured: dict = {}

    def fake_request(method, url, data=None, headers=None, timeout=None):
        captured.update({"method": method, "url": url, "data": data, "headers": headers, "timeout": timeout})
        response = Mock()
        response.raise_for_status.return_value = None
        if url.endswith("/identities/rapid-brightly-firmly-0007"):
            response.json.return_value = {
                "identity": "rapid-brightly-firmly-0007",
                "registration_status": "claimed",
            }
        else:
            response.json.return_value = {"connections": [], "by_source": {"bundled": [], "custom": []}}
        return response

    _patch_httpx_request(monkeypatch, fake_request)

    await AuthsomeApiClient("http://127.0.0.1:7998").list_connections()

    assert captured["headers"]["Authorization"].startswith("PoP ")


@pytest.mark.asyncio
async def test_env_private_key_only_resolves_handle_from_server(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    source = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")
    private_key_hex = RuntimeIdentity.key_path(tmp_path, source.handle).read_text(encoding="utf-8").strip()
    RuntimeIdentity.key_path(tmp_path, source.handle).unlink()
    RuntimeIdentity.metadata_path(tmp_path, source.handle).unlink()
    monkeypatch.setenv("AUTHSOME_IDENTITY_PRIVATE_KEY", private_key_hex)
    resolved_handle = "resolved-from-server-0001"
    calls: list[tuple[str, str]] = []

    def fake_request(method, url, data=None, headers=None, timeout=None):
        calls.append((method, url))
        response = Mock()
        response.status_code = status.HTTP_200_OK
        response.raise_for_status.return_value = None
        if "/api/identities/by-did/" in url:
            response.json.return_value = {"identity": resolved_handle, "did": source.did}
        elif f"/api/identities/{resolved_handle}" in url:
            response.json.return_value = {"identity": resolved_handle, "registration_status": "claimed"}
        else:
            response.json.return_value = {"connections": [], "by_source": {"bundled": [], "custom": []}}
        return response

    _patch_httpx_request(monkeypatch, fake_request)

    identity = await AuthsomeApiClient("http://127.0.0.1:7998").ensure_identity_ready()

    assert identity.handle == resolved_handle
    assert identity.did == source.did
    assert (
        "GET",
        f"http://127.0.0.1:7998/api/identities/by-did/{source.did}",
    ) in calls


@pytest.mark.asyncio
async def test_env_private_key_only_registers_generated_handle_when_did_unknown(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    source = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")
    private_key_hex = RuntimeIdentity.key_path(tmp_path, source.handle).read_text(encoding="utf-8").strip()
    RuntimeIdentity.key_path(tmp_path, source.handle).unlink()
    RuntimeIdentity.metadata_path(tmp_path, source.handle).unlink()
    monkeypatch.setenv("AUTHSOME_IDENTITY_PRIVATE_KEY", private_key_hex)
    registered: dict = {}

    def fake_request(method, url, data=None, headers=None, timeout=None):
        response = Mock()
        if "/api/identities/by-did/" in url:
            response.status_code = status.HTTP_404_NOT_FOUND
            response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Not Found", request=Mock(), response=Mock(status_code=status.HTTP_404_NOT_FOUND)
            )
        elif url.endswith("/api/identities/register"):
            response.status_code = status.HTTP_200_OK
            response.raise_for_status.return_value = None
            registered.update(json.loads(data.decode("utf-8")))
            response.json.return_value = {
                "identity": registered["handle"],
                "did": registered["did"],
                "registration_status": "claimed",
            }
        elif "/api/identities/" in url and method == "GET":
            response.status_code = status.HTTP_404_NOT_FOUND
            response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Not Found", request=Mock(), response=Mock(status_code=status.HTTP_404_NOT_FOUND)
            )
        else:
            response.status_code = status.HTTP_200_OK
            response.raise_for_status.return_value = None
            response.json.return_value = {"connections": [], "by_source": {"bundled": [], "custom": []}}
        return response

    _patch_httpx_request(monkeypatch, fake_request)

    identity = await AuthsomeApiClient("http://127.0.0.1:7998").ensure_identity_ready()

    assert identity.handle is not None
    assert registered["handle"] == identity.handle
    assert registered["did"] == source.did


@pytest.mark.asyncio
async def test_env_identity_does_not_update_active_agent(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    stored = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")
    ClientConfig(active_identity=stored.handle).save(tmp_path)
    private_key_hex = RuntimeIdentity.key_path(tmp_path, stored.handle).read_text(encoding="utf-8").strip()
    monkeypatch.setenv("AUTHSOME_IDENTITY", "rapid-brightly-firmly-0007")
    monkeypatch.setenv("AUTHSOME_IDENTITY_PRIVATE_KEY", private_key_hex)

    client = AuthsomeApiClient("http://127.0.0.1:7998")
    client.get_identity_status = AsyncMock(  # type: ignore[method-assign]
        return_value={"identity": "rapid-brightly-firmly-0007", "registration_status": "claimed"}
    )

    await client.ensure_identity_ready()

    assert ClientConfig.load(tmp_path).active_identity == stored.handle


@pytest.mark.asyncio
async def test_start_login_bootstraps_identity_readiness(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    client = AuthsomeApiClient("http://127.0.0.1:7998")
    client.ensure_identity_ready = AsyncMock()  # type: ignore[method-assign]
    client._post = AsyncMock(return_value={"id": "sess-123", "status": "pending"})  # type: ignore[method-assign]

    result = await client.start_login(provider="github")

    client.ensure_identity_ready.assert_not_awaited()
    client._post.assert_awaited_once_with("/api/auth/sessions", {"provider": "github"})  # type: ignore[attr-defined]
    assert result["id"] == "sess-123"


@pytest.mark.asyncio
async def test_protected_request_bootstraps_identity_readiness(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    captured: dict = {}

    def fake_request(method, url, data=None, headers=None, timeout=None):
        captured.update({"method": method, "url": url, "data": data, "headers": headers, "timeout": timeout})
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"connections": [], "by_source": {"bundled": [], "custom": []}}
        return response

    _patch_httpx_request(monkeypatch, fake_request)

    identity = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")
    client = AuthsomeApiClient("http://127.0.0.1:7998")
    client.ensure_identity_ready = AsyncMock(  # type: ignore[method-assign]
        return_value=RuntimeIdentity.load(tmp_path, env={"AUTHSOME_IDENTITY": identity.handle})
    )

    await client.list_connections()

    client.ensure_identity_ready.assert_awaited_once()
    assert captured["headers"]["Authorization"].startswith("PoP ")


@pytest.mark.asyncio
async def test_in_memory_cache_skips_server_check_on_subsequent_calls(monkeypatch, tmp_path: Path) -> None:
    """After the first successful registration check, the in-memory flag prevents
    further server calls for the lifetime of the client instance."""
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    base_url = "http://127.0.0.1:7998"
    identity = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")
    ClientConfig(active_identity=identity.handle).save(tmp_path)
    calls: list[tuple[str, str]] = []

    def fake_request(method, url, data=None, headers=None, timeout=None):
        calls.append((method, url))
        response = Mock()
        response.raise_for_status.return_value = None
        if f"/api/identities/{identity.handle}" in url:
            response.json.return_value = {"identity": identity.handle, "registration_status": "claimed"}
        else:
            response.json.return_value = {"connections": [], "by_source": {"bundled": [], "custom": []}}
        return response

    _patch_httpx_request(monkeypatch, fake_request)

    client = AuthsomeApiClient(base_url)
    await client.list_connections()
    await client.list_connections()

    assert calls == [
        ("GET", f"http://127.0.0.1:7998/api/identities/{identity.handle}"),
        ("GET", "http://127.0.0.1:7998/api/connections"),
        ("GET", "http://127.0.0.1:7998/api/connections"),
    ]
