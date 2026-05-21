
import pytest

from authsome.auth.flows.browser_sso import BrowserSSOFlow, _parse_ttl_duration
from authsome.auth.models.connection import ConnectionRecord
from authsome.auth.models.enums import AuthType, ConnectionStatus
from authsome.auth.models.provider import ProviderDefinition
from authsome.auth.sessions import AuthSession


def _make_provider(ttl: str | None = None) -> ProviderDefinition:
    return ProviderDefinition.model_validate({
        "schema_version": 1,
        "name": "x-browser",
        "display_name": "X Browser SSO",
        "auth_type": "browser_sso",
        "flow": "browser_sso",
        "browser_sso": {
            "entry_url": "https://x.com/",
            "domains": ["x.com", "twitter.com"],
            "validate_url": "https://x.com/i/api/2/notifications/all.json?count=1",
            "extract": [
                {"from": "cookies", "as": "cookie", "match": "*"},
                {"from": "cookies", "as": "ct0", "match": "ct0"},
            ],
            "extra_headers": {"Cookie": "${cookie}", "x-csrf-token": "${ct0}"},
            **({"ttl": ttl} if ttl else {}),
        },
    })


def _make_session() -> AuthSession:
    return AuthSession(
        session_id="sess_test123",
        provider="x-browser",
        identity="test-agent",
        connection_name="default",
        flow_type="browser_sso",
    )


# --- _parse_ttl_duration ---

def test_parse_ttl_duration_days():
    from datetime import timedelta
    assert _parse_ttl_duration("30d") == timedelta(days=30)


def test_parse_ttl_duration_hours():
    from datetime import timedelta
    assert _parse_ttl_duration("24h") == timedelta(hours=24)


def test_parse_ttl_duration_minutes():
    from datetime import timedelta
    assert _parse_ttl_duration("90m") == timedelta(minutes=90)


def test_parse_ttl_duration_none():
    assert _parse_ttl_duration(None) is None


def test_parse_ttl_duration_invalid_returns_none():
    assert _parse_ttl_duration("invalid") is None


# --- BrowserSSOFlow.begin() ---

@pytest.mark.asyncio
async def test_begin_sets_waiting_for_user():
    flow = BrowserSSOFlow()
    session = _make_session()
    provider = _make_provider()
    await flow.begin(provider, "test-agent", "default", session)
    assert session.state == "waiting_for_user"


@pytest.mark.asyncio
async def test_begin_stores_entry_url_in_payload():
    flow = BrowserSSOFlow()
    session = _make_session()
    provider = _make_provider()
    await flow.begin(provider, "test-agent", "default", session)
    assert session.payload["entry_url"] == "https://x.com/"
    assert session.payload["domains"] == ["x.com", "twitter.com"]
    assert session.payload["validate_url"] == "https://x.com/i/api/2/notifications/all.json?count=1"


@pytest.mark.asyncio
async def test_begin_requires_browser_sso_config():
    from authsome.errors import AuthenticationFailedError
    flow = BrowserSSOFlow()
    session = _make_session()
    bad_provider = ProviderDefinition.model_validate({
        "schema_version": 1,
        "name": "x-browser",
        "display_name": "X",
        "auth_type": "browser_sso",
        "flow": "browser_sso",
    })
    # browser_sso defaults to None — no object.__setattr__ needed
    with pytest.raises(AuthenticationFailedError, match="browser_sso"):
        await flow.begin(bad_provider, "test-agent", "default", session)


# --- BrowserSSOFlow.resume() ---

@pytest.mark.asyncio
async def test_resume_builds_connected_record():
    flow = BrowserSSOFlow()
    session = _make_session()
    provider = _make_provider()
    callback_data = {"credentials": {"cookie": "abc=123", "ct0": "xyz"}}
    result = await flow.resume(provider, "test-agent", "default", session, callback_data)
    assert result is not None
    assert result.connection.auth_type == AuthType.BROWSER_SSO
    assert result.connection.status == ConnectionStatus.CONNECTED
    assert result.connection.credentials == {"cookie": "abc=123", "ct0": "xyz"}
    assert result.connection.provider == "x-browser"
    assert result.connection.identity == "test-agent"


@pytest.mark.asyncio
async def test_resume_sets_expires_at_from_ttl():
    flow = BrowserSSOFlow()
    session = _make_session()
    provider = _make_provider(ttl="30d")
    callback_data = {"credentials": {"cookie": "abc=123", "ct0": "xyz"}}
    result = await flow.resume(provider, "test-agent", "default", session, callback_data)
    assert result.connection.expires_at is not None
    from datetime import timedelta

    from authsome.utils import utc_now
    expected_delta = timedelta(days=30)
    diff = result.connection.expires_at - utc_now()
    assert abs((diff - expected_delta).total_seconds()) < 5


@pytest.mark.asyncio
async def test_resume_no_ttl_means_no_expires_at():
    flow = BrowserSSOFlow()
    session = _make_session()
    provider = _make_provider(ttl=None)
    callback_data = {"credentials": {"cookie": "abc=123", "ct0": "xyz"}}
    result = await flow.resume(provider, "test-agent", "default", session, callback_data)
    assert result.connection.expires_at is None


@pytest.mark.asyncio
async def test_resume_missing_credentials_raises():
    from authsome.errors import AuthenticationFailedError
    flow = BrowserSSOFlow()
    session = _make_session()
    provider = _make_provider()
    with pytest.raises(AuthenticationFailedError, match="credentials"):
        await flow.resume(provider, "test-agent", "default", session, {})


@pytest.mark.asyncio
async def test_resume_empty_credentials_raises():
    from authsome.errors import AuthenticationFailedError
    flow = BrowserSSOFlow()
    session = _make_session()
    provider = _make_provider()
    with pytest.raises(AuthenticationFailedError, match="credentials"):
        await flow.resume(provider, "test-agent", "default", session, {"credentials": {}})


def test_refresh_raises_refresh_failed_error():
    from authsome.errors import RefreshFailedError
    flow = BrowserSSOFlow()
    provider = _make_provider()
    record = ConnectionRecord(
        provider="x-browser",
        identity="agent",
        connection_name="default",
        auth_type=AuthType.BROWSER_SSO,
        status=ConnectionStatus.CONNECTED,
        credentials={"cookie": "abc"},
    )
    with pytest.raises(RefreshFailedError):
        flow.refresh(provider, record)
