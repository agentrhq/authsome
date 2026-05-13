"""Tests for authentication flows."""

import pytest

from authsome.auth.flows.api_key import ApiKeyFlow
from authsome.auth.models.enums import AuthType, ConnectionStatus, FlowType
from authsome.auth.models.provider import ApiKeyConfig, ProviderDefinition
from authsome.errors import AuthenticationFailedError


def _make_api_key_provider() -> ProviderDefinition:
    return ProviderDefinition(
        name="testapi",
        display_name="Test API",
        auth_type=AuthType.API_KEY,
        flow=FlowType.API_KEY,
        api_key=ApiKeyConfig(
            header_name="Authorization",
            header_prefix="Bearer",
        ),
    )


@pytest.mark.asyncio
class TestApiKeyFlow:
    """API key flow tests."""

    async def test_successful_login(self) -> None:
        from unittest.mock import Mock

        flow = ApiKeyFlow()
        provider = _make_api_key_provider()
        session = Mock()
        session.payload = {"api_key": "sk-test-key-123"}

        result = await flow.resume(
            provider=provider,
            identity="default",
            connection_name="default",
            runtime_session=session,
            callback_data={},
        )
        record = result.connection

        assert record.provider == "testapi"
        assert record.identity == "default"
        assert record.connection_name == "default"
        assert record.auth_type == AuthType.API_KEY
        assert record.status == ConnectionStatus.CONNECTED
        # Token is stored as plaintext
        assert record.api_key == "sk-test-key-123"
        assert record.schema_version == 2

    async def test_empty_key_rejected(self) -> None:
        from unittest.mock import Mock

        flow = ApiKeyFlow()
        provider = _make_api_key_provider()
        session = Mock()
        session.payload = {"api_key": ""}

        with pytest.raises(AuthenticationFailedError, match="cannot be empty"):
            await flow.resume(
                provider=provider,
                identity="default",
                connection_name="default",
                runtime_session=session,
                callback_data={},
            )

    async def test_whitespace_only_rejected(self) -> None:
        from unittest.mock import Mock

        flow = ApiKeyFlow()
        provider = _make_api_key_provider()
        session = Mock()
        session.payload = {"api_key": "   "}

        with pytest.raises(AuthenticationFailedError, match="cannot be empty"):
            await flow.resume(
                provider=provider,
                identity="default",
                connection_name="default",
                runtime_session=session,
                callback_data={},
            )

    async def test_missing_api_key_config(self) -> None:
        from unittest.mock import Mock

        flow = ApiKeyFlow()
        provider = ProviderDefinition(
            name="noconfig",
            display_name="No Config",
            auth_type=AuthType.API_KEY,
            flow=FlowType.API_KEY,
        )
        session = Mock()
        session.payload = {"api_key": "sk-test-key-123"}

        with pytest.raises(AuthenticationFailedError, match="missing 'api_key'"):
            await flow.resume(
                provider=provider,
                identity="default",
                connection_name="default",
                runtime_session=session,
                callback_data={},
            )

    async def test_missing_api_key_parameter(self) -> None:
        from unittest.mock import Mock

        flow = ApiKeyFlow()
        provider = _make_api_key_provider()
        session = Mock()
        session.payload = {"api_key": None}

        with pytest.raises(AuthenticationFailedError, match="cannot be empty"):
            await flow.resume(
                provider=provider,
                identity="default",
                connection_name="default",
                runtime_session=session,
                callback_data={},
            )

    async def test_api_key_stripped(self) -> None:
        from unittest.mock import Mock

        flow = ApiKeyFlow()
        provider = _make_api_key_provider()
        session = Mock()
        session.payload = {"api_key": "  sk-test-key-123  "}

        result = await flow.resume(
            provider=provider,
            identity="default",
            connection_name="default",
            runtime_session=session,
            callback_data={},
        )
        assert result.connection.api_key == "sk-test-key-123"

    async def test_key_pattern_match_succeeds(self) -> None:
        from unittest.mock import Mock

        flow = ApiKeyFlow()
        provider = ProviderDefinition(
            name="testapi",
            display_name="Test API",
            auth_type=AuthType.API_KEY,
            flow=FlowType.API_KEY,
            api_key=ApiKeyConfig(
                key_pattern=r"^sk-[A-Za-z0-9_-]{8,}$",
                key_pattern_hint="Keys start with 'sk-'.",
            ),
        )
        session = Mock()
        session.payload = {"api_key": "sk-abcdefgh12345"}

        result = await flow.resume(
            provider=provider,
            identity="default",
            connection_name="default",
            runtime_session=session,
            callback_data={},
        )
        assert result.connection.api_key == "sk-abcdefgh12345"

    async def test_key_pattern_mismatch_uses_hint(self) -> None:
        from unittest.mock import Mock

        flow = ApiKeyFlow()
        provider = ProviderDefinition(
            name="testapi",
            display_name="Test API",
            auth_type=AuthType.API_KEY,
            flow=FlowType.API_KEY,
            api_key=ApiKeyConfig(
                key_pattern=r"^sk-[A-Za-z0-9_-]{8,}$",
                key_pattern_hint="Keys start with 'sk-'.",
            ),
        )
        session = Mock()
        session.payload = {"api_key": "982832"}

        with pytest.raises(AuthenticationFailedError, match="Keys start with 'sk-'"):
            await flow.resume(
                provider=provider,
                identity="default",
                connection_name="default",
                runtime_session=session,
                callback_data={},
            )

    async def test_key_pattern_mismatch_default_message(self) -> None:
        from unittest.mock import Mock

        flow = ApiKeyFlow()
        provider = ProviderDefinition(
            name="testapi",
            display_name="Test API",
            auth_type=AuthType.API_KEY,
            flow=FlowType.API_KEY,
            api_key=ApiKeyConfig(key_pattern=r"^sk-.+$"),
        )
        session = Mock()
        session.payload = {"api_key": "982832"}

        with pytest.raises(AuthenticationFailedError, match="doesn't match the expected format"):
            await flow.resume(
                provider=provider,
                identity="default",
                connection_name="default",
                runtime_session=session,
                callback_data={},
            )

    async def test_no_pattern_skips_validation(self) -> None:
        from unittest.mock import Mock

        flow = ApiKeyFlow()
        provider = _make_api_key_provider()  # no key_pattern
        session = Mock()
        session.payload = {"api_key": "982832"}

        result = await flow.resume(
            provider=provider,
            identity="default",
            connection_name="default",
            runtime_session=session,
            callback_data={},
        )
        assert result.connection.api_key == "982832"

    async def test_resume_uses_callback_data_api_key_when_session_payload_missing(self) -> None:
        from unittest.mock import Mock

        flow = ApiKeyFlow()
        provider = _make_api_key_provider()
        session = Mock()
        session.payload = {}

        result = await flow.resume(
            provider=provider,
            identity="default",
            connection_name="default",
            runtime_session=session,
            callback_data={"api_key": "sk-from-callback"},
        )
        assert result.connection.api_key == "sk-from-callback"
