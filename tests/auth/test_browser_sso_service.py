"""Tests for Browser SSO plumbing in AuthService (service.py)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from authsome.auth.models.connection import ConnectionRecord
from authsome.auth.models.enums import AuthType, ConnectionStatus
from authsome.auth.models.provider import ProviderDefinition
from authsome.errors import TokenExpiredError
from authsome.server.credential_service import _render_extra_headers, _validate_browser_sso_credentials

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_browser_provider(validate_url: str | None = "https://example.com/validate") -> ProviderDefinition:
    return ProviderDefinition.model_validate(
        {
            "schema_version": 1,
            "name": "test-browser",
            "display_name": "Test Browser SSO",
            "auth_type": "browser_sso",
            "flow": "browser_sso",
            "browser_sso": {
                "entry_url": "https://example.com/login",
                "domains": ["example.com"],
                "validate_url": validate_url,
                "extract": [
                    {"from": "cookies", "as": "cookie", "match": "*"},
                    {"from": "cookies", "as": "ct0", "match": "ct0"},
                ],
                "extra_headers": {"Cookie": "${cookie}", "x-csrf-token": "${ct0}"},
            },
        }
    )


def _make_connection_record(credentials: dict[str, str] | None = None) -> ConnectionRecord:
    return ConnectionRecord(
        schema_version=2,
        provider="test-browser",
        identity="test-agent",
        connection_name="default",
        auth_type=AuthType.BROWSER_SSO,
        status=ConnectionStatus.CONNECTED,
        credentials=credentials or {"cookie": "abc=123", "ct0": "deadbeef"},
    )


# ── _render_extra_headers ─────────────────────────────────────────────────────


def test_render_extra_headers_substitution():
    extra_headers = {"Cookie": "${cookie}", "x-csrf-token": "${ct0}"}
    credentials = {"cookie": "abc=123", "ct0": "deadbeef"}
    result = _render_extra_headers(extra_headers, credentials)
    assert result == {"Cookie": "abc=123", "x-csrf-token": "deadbeef"}


def test_render_extra_headers_static_passthrough():
    extra_headers = {"Authorization": "Bearer AAAAA"}
    credentials: dict[str, str] = {}
    result = _render_extra_headers(extra_headers, credentials)
    assert result == {"Authorization": "Bearer AAAAA"}


def test_render_extra_headers_missing_key_empty_string():
    extra_headers = {"Cookie": "${missing}"}
    credentials: dict[str, str] = {}
    result = _render_extra_headers(extra_headers, credentials)
    assert result == {"Cookie": ""}


def test_render_extra_headers_mixed():
    extra_headers = {"Cookie": "${cookie}", "X-Static": "static-value", "x-csrf-token": "${ct0}"}
    credentials = {"cookie": "sess=xyz", "ct0": "tok123"}
    result = _render_extra_headers(extra_headers, credentials)
    assert result == {"Cookie": "sess=xyz", "X-Static": "static-value", "x-csrf-token": "tok123"}


def test_render_extra_headers_empty():
    result = _render_extra_headers({}, {"cookie": "x"})
    assert result == {}


# ── _validate_browser_sso_credentials ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_validate_browser_sso_credentials_200_does_not_raise():
    record = _make_connection_record()
    definition = _make_browser_provider()

    mock_response = MagicMock()
    mock_response.status_code = 200

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("authsome.auth.service.httpx.AsyncClient", return_value=mock_client):
        await _validate_browser_sso_credentials(record, definition)


@pytest.mark.asyncio
async def test_validate_browser_sso_credentials_401_raises_token_expired():
    record = _make_connection_record()
    definition = _make_browser_provider()

    mock_response = MagicMock()
    mock_response.status_code = 401

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("authsome.auth.service.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(TokenExpiredError):
            await _validate_browser_sso_credentials(record, definition)


@pytest.mark.asyncio
async def test_validate_browser_sso_credentials_403_raises_token_expired():
    record = _make_connection_record()
    definition = _make_browser_provider()

    mock_response = MagicMock()
    mock_response.status_code = 403

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch("authsome.auth.service.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(TokenExpiredError):
            await _validate_browser_sso_credentials(record, definition)


@pytest.mark.asyncio
async def test_validate_browser_sso_credentials_network_error_tolerated():
    record = _make_connection_record()
    definition = _make_browser_provider()

    mock_client = AsyncMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.get = AsyncMock(side_effect=OSError("Connection refused"))

    with patch("authsome.auth.service.httpx.AsyncClient", return_value=mock_client):
        # Should not raise — network errors are tolerated
        await _validate_browser_sso_credentials(record, definition)


@pytest.mark.asyncio
async def test_validate_browser_sso_credentials_no_validate_url_returns_immediately():
    record = _make_connection_record()
    definition = _make_browser_provider(validate_url=None)

    # httpx should never be called
    with patch("authsome.auth.service.httpx.AsyncClient") as mock_cls:
        await _validate_browser_sso_credentials(record, definition)
        mock_cls.assert_not_called()


# ── _get_auth_headers_from_record (BROWSER_SSO) ───────────────────────────────


@pytest.mark.asyncio
async def test_get_auth_headers_from_record_browser_sso():
    """BROWSER_SSO branch must run BEFORE _get_access_token_from_record, not dead code."""
    from unittest.mock import MagicMock

    from authsome.auth.models.connection import ConnectionRecord
    from authsome.auth.models.enums import AuthType, ConnectionStatus
    from authsome.auth.models.provider import ProviderDefinition
    from authsome.server.credential_service import AuthService
    from authsome.vault import Vault

    record = ConnectionRecord(
        provider="x-browser",
        identity="agent",
        connection_name="default",
        auth_type=AuthType.BROWSER_SSO,
        status=ConnectionStatus.CONNECTED,
        credentials={"cookie": "auth_token=abc; ct0=xyz", "ct0": "xyz"},
    )
    provider = ProviderDefinition.model_validate(
        {
            "schema_version": 1,
            "name": "x-browser",
            "display_name": "X",
            "auth_type": "browser_sso",
            "flow": "browser_sso",
            "browser_sso": {
                "entry_url": "https://x.com/",
                "domains": ["x.com"],
                "validate_url": None,  # skip network call
                "extract": [{"from": "cookies", "as": "cookie", "match": "*"}],
                "extra_headers": {"Cookie": "${cookie}", "x-csrf-token": "${ct0}"},
            },
        }
    )

    vault = MagicMock(spec=Vault)
    svc = AuthService(vault=vault, identity="agent", principal_id="default", vault_id="default")

    headers = await svc._get_auth_headers_from_record(record, provider)
    assert headers["Cookie"] == "auth_token=abc; ct0=xyz"
    assert headers["x-csrf-token"] == "xyz"
