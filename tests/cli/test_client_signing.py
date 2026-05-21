import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from authsome.cli.client import AuthsomeApiClient
from authsome.cli.client_config import ClientConfig, load_client_config, save_client_config
from authsome.identity import create_identity, mark_claimed, mark_registered


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

    monkeypatch.setattr("authsome.cli.client.requests.request", fake_request)

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

    monkeypatch.setattr("authsome.cli.client.requests.request", fake_request)

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

    monkeypatch.setattr("authsome.cli.client.requests.request", fake_request)

    await AuthsomeApiClient("http://127.0.0.1:7998").set_default_connection("github", "work")

    assert captured["data"] == json.dumps({}, separators=(",", ":"), sort_keys=True).encode("utf-8")


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

    monkeypatch.setattr("authsome.cli.client.requests.request", fake_request)

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

    monkeypatch.setattr("authsome.cli.client.requests.request", fake_request)

    await AuthsomeApiClient("http://127.0.0.1:7998").resolve_credentials(provider="github", connection="default")

    assert captured["method"] == "POST"
    assert captured["url"].endswith("/credentials/resolve")
    assert captured["headers"]["Authorization"].startswith("PoP ")


@pytest.mark.asyncio
async def test_registered_identity_skips_reregister_roundtrip(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    identity = create_identity(tmp_path, "steady-wisely-boldly-0042")
    mark_registered(tmp_path, identity.handle)
    mark_claimed(tmp_path, identity.handle)
    save_client_config(tmp_path, ClientConfig(active_identity=identity.handle))
    calls: list[tuple[str, str]] = []

    def fake_request(method, url, data=None, headers=None, timeout=None):
        calls.append((method, url))
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"connections": [], "by_source": {"bundled": [], "custom": []}}
        return response

    monkeypatch.setattr("authsome.cli.client.requests.request", fake_request)

    await AuthsomeApiClient("http://127.0.0.1:7998").list_connections()

    assert calls == [("GET", "http://127.0.0.1:7998/connections")]


@pytest.mark.asyncio
async def test_bootstrapped_identity_is_saved_as_active_profile(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    captured: dict = {}

    def fake_request(method, url, data=None, headers=None, timeout=None):
        captured.update({"method": method, "url": url, "data": data, "headers": headers, "timeout": timeout})
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"connections": [], "by_source": {"bundled": [], "custom": []}}
        return response

    monkeypatch.setattr("authsome.cli.client.requests.request", fake_request)

    await AuthsomeApiClient("http://127.0.0.1:7998").list_connections()

    config = load_client_config(tmp_path)
    assert config.active_identity is not None


@pytest.mark.asyncio
async def test_identity_env_override_wins_over_active_identity(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    monkeypatch.setenv("AUTHSOME_IDENTITY", "rapid-brightly-firmly-0007")
    create_identity(tmp_path, "steady-wisely-boldly-0042")
    override_identity = create_identity(tmp_path, "rapid-brightly-firmly-0007")
    mark_registered(tmp_path, override_identity.handle)
    mark_claimed(tmp_path, override_identity.handle)
    save_client_config(tmp_path, ClientConfig(active_identity="steady-wisely-boldly-0042"))

    client = AuthsomeApiClient("http://127.0.0.1:7998")
    identity = await client.ensure_identity_ready()

    assert identity.handle == "rapid-brightly-firmly-0007"


@pytest.mark.asyncio
async def test_start_login_bootstraps_identity_readiness(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    client = AuthsomeApiClient("http://127.0.0.1:7998")
    client.ensure_identity_ready = AsyncMock()  # type: ignore[method-assign]
    client._post = AsyncMock(return_value={"id": "sess-123", "status": "pending"})  # type: ignore[method-assign]

    result = await client.start_login(provider="github")

    client.ensure_identity_ready.assert_not_awaited()
    client._post.assert_awaited_once_with("/auth/sessions", {"provider": "github"})  # type: ignore[attr-defined]
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

    monkeypatch.setattr("authsome.cli.client.requests.request", fake_request)

    client = AuthsomeApiClient("http://127.0.0.1:7998")
    client.ensure_identity_ready = AsyncMock(  # type: ignore[method-assign]
        return_value=create_identity(tmp_path, "steady-wisely-boldly-0042")
    )

    await client.list_connections()

    client.ensure_identity_ready.assert_awaited_once()
    assert captured["headers"]["Authorization"].startswith("PoP ")


@pytest.mark.asyncio
async def test_status_check_marks_identity_claimed_and_skips_future_roundtrip(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
    identity = create_identity(tmp_path, "steady-wisely-boldly-0042")
    mark_registered(tmp_path, identity.handle)
    save_client_config(tmp_path, ClientConfig(active_identity=identity.handle))
    calls: list[tuple[str, str]] = []

    def fake_request(method, url, data=None, headers=None, timeout=None):
        calls.append((method, url))
        response = Mock()
        response.raise_for_status.return_value = None
        if url.endswith(f"/identities/{identity.handle}"):
            response.json.return_value = {
                "identity": identity.handle,
                "did": identity.did,
                "registration_status": "claimed",
                "principal_id": "principal_123",
            }
        else:
            response.json.return_value = {"connections": [], "by_source": {"bundled": [], "custom": []}}
        return response

    monkeypatch.setattr("authsome.cli.client.requests.request", fake_request)

    client = AuthsomeApiClient("http://127.0.0.1:7998")
    await client.list_connections()
    await client.list_connections()

    assert calls == [
        ("GET", f"http://127.0.0.1:7998/identities/{identity.handle}"),
        ("GET", "http://127.0.0.1:7998/connections"),
        ("GET", "http://127.0.0.1:7998/connections"),
    ]
