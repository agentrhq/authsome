"""Tests for BROWSER auth handling in credential_service.py."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

import pytest

from authsome.auth.models.connection import ConnectionRecord
from authsome.auth.models.enums import AuthType, ConnectionStatus, FlowType
from authsome.auth.models.provider import BrowserConfig, ExtractRule, ProviderDefinition
from authsome.errors import CredentialMissingError, TokenExpiredError
from authsome.server.credential_repository import CredentialRepository
from authsome.server.credential_service import CredentialService
from authsome.utils import utc_now


class StaticProviders:
    async def get(self, name: str):  # noqa: ANN001, ANN201
        return _provider()

    async def list(self):  # noqa: ANN201
        return [_provider()]

    async def list_by_source(self):  # noqa: ANN201
        return {"bundled": [_provider()], "custom": []}

    async def save_custom(self, definition, *, force: bool = False) -> None:  # noqa: ANN001
        raise AssertionError("unexpected provider save")

    async def delete_custom(self, name: str) -> bool:
        return False

    async def is_custom(self, name: str) -> bool:
        return False


def _svc() -> CredentialService:
    vault = MagicMock()
    return CredentialService(
        credentials=CredentialRepository(vault, identity="agent", principal_id="p1", vault_id="v1"),
        providers=StaticProviders(),
        identity="agent",
        principal_id="p1",
        vault_id="v1",
    )


def _provider(validate_url: str | None = None) -> ProviderDefinition:
    return ProviderDefinition(
        schema_version=1,
        name="x-browser",
        display_name="X Browser",
        auth_type=AuthType.BROWSER,
        flow=FlowType.BROWSER,
        browser=BrowserConfig(
            entry_url="https://x.com/login",
            domains=[".x.com"],
            auth_cookies=["auth_token"],
            extra_headers={"x-twitter-active-user": "yes"},
            extract=[ExtractRule(cookie="ct0", header="x-csrf-token")],
        ),
    )


def _record(
    credentials: dict[str, str] | None = None,
    expires_at=None,
) -> ConnectionRecord:
    return ConnectionRecord(
        provider="x-browser",
        connection_name="default",
        auth_type=AuthType.BROWSER,
        status=ConnectionStatus.CONNECTED,
        credentials=credentials if credentials is not None else {"auth_token": "tok", "ct0": "csrf"},
        expires_at=expires_at,
    )


# ── _get_auth_headers_from_record (BROWSER) ───────────────────────────────────


@pytest.mark.asyncio
async def test_browser_headers_include_cookie_header():
    svc = _svc()
    headers = await svc._get_auth_headers_from_record(_record(), _provider())
    assert "Cookie" in headers
    assert "auth_token=tok" in headers["Cookie"]
    assert "ct0=csrf" in headers["Cookie"]


@pytest.mark.asyncio
async def test_browser_headers_apply_extract_rules():
    svc = _svc()
    headers = await svc._get_auth_headers_from_record(_record(), _provider())
    assert headers["x-csrf-token"] == "csrf"


@pytest.mark.asyncio
async def test_browser_headers_include_extra_headers():
    svc = _svc()
    headers = await svc._get_auth_headers_from_record(_record(), _provider())
    assert headers["x-twitter-active-user"] == "yes"


@pytest.mark.asyncio
async def test_browser_headers_raises_when_no_credentials():
    svc = _svc()
    with pytest.raises(CredentialMissingError):
        await svc._get_auth_headers_from_record(_record(credentials={}), _provider())


@pytest.mark.asyncio
async def test_browser_headers_raises_when_credentials_none():
    svc = _svc()
    record = ConnectionRecord(
        provider="x-browser",
        connection_name="default",
        auth_type=AuthType.BROWSER,
        status=ConnectionStatus.CONNECTED,
        credentials=None,
    )
    with pytest.raises(CredentialMissingError):
        await svc._get_auth_headers_from_record(record, _provider())


@pytest.mark.asyncio
async def test_browser_headers_raises_token_expired_when_past_expiry():
    svc = _svc()
    expired_record = _record(expires_at=utc_now() - timedelta(hours=1))
    with pytest.raises(TokenExpiredError):
        await svc._get_auth_headers_from_record(expired_record, _provider())


@pytest.mark.asyncio
async def test_browser_headers_ok_when_expiry_in_future():
    svc = _svc()
    valid_record = _record(expires_at=utc_now() + timedelta(hours=23))
    headers = await svc._get_auth_headers_from_record(valid_record, _provider())
    assert "Cookie" in headers


@pytest.mark.asyncio
async def test_browser_headers_ok_when_no_expiry_set():
    svc = _svc()
    headers = await svc._get_auth_headers_from_record(_record(expires_at=None), _provider())
    assert "Cookie" in headers


# ── _validate_provider (BROWSER) ──────────────────────────────────────────────


def test_validate_browser_provider_ok():
    svc = _svc()
    svc._validate_provider(_provider())  # should not raise


def test_validate_browser_provider_missing_browser_config():
    from authsome.errors import InvalidProviderSchemaError

    svc = _svc()
    bad = ProviderDefinition(
        schema_version=1,
        name="x-browser",
        display_name="X",
        auth_type=AuthType.BROWSER,
        flow=FlowType.BROWSER,
    )
    with pytest.raises(InvalidProviderSchemaError, match="browser"):
        svc._validate_provider(bad)
