"""Tests for BrowserFlow begin/resume/refresh."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from authsome.auth.flows.browser import BrowserFlow
from authsome.auth.models.connection import ConnectionRecord
from authsome.auth.models.enums import AuthType, ConnectionStatus, FlowType
from authsome.auth.models.provider import BrowserConfig, ExtractRule, ProviderDefinition
from authsome.errors import AuthenticationFailedError, RefreshFailedError


def _provider(ttl_hours: int = 24) -> ProviderDefinition:
    return ProviderDefinition(
        schema_version=1,
        name="x-browser",
        display_name="X Browser",
        auth_type=AuthType.BROWSER,
        flow=FlowType.BROWSER,
        browser=BrowserConfig(
            entry_url="https://x.com/login",
            domains=[".x.com", "x.com"],
            auth_cookies=["auth_token"],
            ttl_hours=ttl_hours,
            extract=[ExtractRule(cookie="ct0", header="x-csrf-token")],
        ),
    )


def _provider_no_browser() -> ProviderDefinition:
    return ProviderDefinition(
        schema_version=1,
        name="x-browser",
        display_name="X Browser",
        auth_type=AuthType.BROWSER,
        flow=FlowType.BROWSER,
    )


def _session() -> MagicMock:
    s = MagicMock()
    s.state = "pending"
    s.payload = {}
    return s


# ── begin() ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_begin_sets_waiting_for_user():
    session = _session()
    await BrowserFlow().begin(_provider(), "agent", "default", session)
    assert session.state == "waiting_for_user"


@pytest.mark.asyncio
async def test_begin_stores_browser_login_flag():
    session = _session()
    await BrowserFlow().begin(_provider(), "agent", "default", session)
    assert session.payload["browser_login"] is True


@pytest.mark.asyncio
async def test_begin_stores_entry_url_and_domains():
    session = _session()
    await BrowserFlow().begin(_provider(), "agent", "default", session)
    assert session.payload["entry_url"] == "https://x.com/login"
    assert session.payload["domains"] == [".x.com", "x.com"]
    assert session.payload["auth_cookies"] == ["auth_token"]


@pytest.mark.asyncio
async def test_begin_raises_when_browser_config_missing():
    session = _session()
    with pytest.raises(AuthenticationFailedError, match="browser"):
        await BrowserFlow().begin(_provider_no_browser(), "agent", "default", session)


# ── resume() ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_resume_returns_connected_record():
    session = _session()
    result = await BrowserFlow().resume(
        _provider(),
        "agent",
        "default",
        session,
        {"credentials": {"auth_token": "tok", "ct0": "csrf"}},
    )
    assert result is not None
    assert result.connection.auth_type == AuthType.BROWSER
    assert result.connection.status == ConnectionStatus.CONNECTED
    assert result.connection.credentials == {"auth_token": "tok", "ct0": "csrf"}
    assert result.connection.provider == "x-browser"
    assert result.connection.identity == "agent"


@pytest.mark.asyncio
async def test_resume_sets_expires_at_from_ttl():
    from datetime import timedelta

    from authsome.utils import utc_now

    session = _session()
    result = await BrowserFlow().resume(
        _provider(ttl_hours=48),
        "agent",
        "default",
        session,
        {"credentials": {"auth_token": "tok"}},
    )
    assert result is not None
    assert result.connection.expires_at is not None
    diff = result.connection.expires_at - utc_now()
    assert abs((diff - timedelta(hours=48)).total_seconds()) < 5


@pytest.mark.asyncio
async def test_resume_returns_none_when_credentials_absent():
    session = _session()
    result = await BrowserFlow().resume(_provider(), "agent", "default", session, {})
    assert result is None


@pytest.mark.asyncio
async def test_resume_returns_none_when_credentials_empty_dict():
    session = _session()
    result = await BrowserFlow().resume(_provider(), "agent", "default", session, {"credentials": {}})
    assert result is None


@pytest.mark.asyncio
async def test_resume_raises_when_browser_config_missing():
    session = _session()
    with pytest.raises(AuthenticationFailedError):
        await BrowserFlow().resume(
            _provider_no_browser(),
            "agent",
            "default",
            session,
            {"credentials": {"auth_token": "tok"}},
        )


# ── refresh() ─────────────────────────────────────────────────────────────────


def test_refresh_raises_refresh_failed_error():
    record = ConnectionRecord(
        provider="x-browser",
        connection_name="default",
        auth_type=AuthType.BROWSER,
        status=ConnectionStatus.CONNECTED,
        credentials={"auth_token": "tok"},
    )
    with pytest.raises(RefreshFailedError):
        BrowserFlow().refresh(_provider(), record)
