"""Tests for AuthService business logic."""

import json
from datetime import timedelta
from pathlib import Path
from unittest import mock

import pytest

from authsome import audit
from authsome.auth.models.connection import ConnectionRecord
from authsome.auth.models.enums import AuthType, ConnectionStatus
from authsome.auth.service import AuthService
from authsome.errors import RefreshFailedError
from authsome.utils import utc_now


@pytest.mark.asyncio
class TestAuthServiceRefreshLogs:
    """Tests validating that token refresh failure writes correct logs and audit trails."""

    @pytest.fixture
    def audit_log(self, tmp_path: Path) -> Path:
        log_file = tmp_path / "audit.log"
        audit.setup(log_file)
        yield log_file
        audit.clear()

    @pytest.fixture
    def service(self) -> AuthService:
        mock_vault = mock.AsyncMock()
        return AuthService(mock_vault, identity="test-profile", vault_id="test-vault")

    async def test_refresh_failure_fallback_available(self, audit_log: Path, service: AuthService):
        """Verify behavior when refresh fails but current token is valid (close to expiry)."""
        now = utc_now()
        # Close to expiry (<5m) triggers auto-refresh
        expires_at = now + timedelta(minutes=4)

        record = ConnectionRecord(
            provider="github",
            identity="test-profile",
            connection_name="default",
            auth_type=AuthType.OAUTH2,
            status=ConnectionStatus.CONNECTED,
            access_token="original-token",
            refresh_token="original-refresh",
            expires_at=expires_at,
        )

        with mock.patch.object(
            service, "_refresh_token", side_effect=RefreshFailedError("API down", provider="github")
        ):
            with mock.patch("loguru.logger.warning") as mock_logger:
                # Exercise
                token = await service._get_oauth_token(record, provider="github", connection="default")

                # 1. Should yield fallback token
                assert token == "original-token"

                # 2. Log verified
                mock_logger.assert_called_once()
                log_msg = mock_logger.call_args[0][0]
                assert "Warning: token refresh failed for github/default" in log_msg
                assert "using existing token" in log_msg
                assert "expires in " in log_msg

                # 3. Audit verified
                lines = audit_log.read_text().splitlines()
                assert len(lines) == 1
                entry = json.loads(lines[0])
                assert entry["event"] == "refresh_failed"
                assert entry["fallback_available"] is True
                assert "API down" in entry["error"]

    async def test_refresh_failure_expired(self, audit_log: Path, service: AuthService):
        """Verify behavior when refresh fails and current token is already expired."""
        now = utc_now()
        # Already expired
        expires_at = now - timedelta(minutes=10)

        record = ConnectionRecord(
            provider="github",
            identity="test-profile",
            connection_name="default",
            auth_type=AuthType.OAUTH2,
            status=ConnectionStatus.CONNECTED,
            access_token="old-token",
            refresh_token="some-refresh",
            expires_at=expires_at,
        )

        with mock.patch.object(
            service, "_refresh_token", side_effect=RefreshFailedError("API rejected", provider="github")
        ):
            with mock.patch("loguru.logger.warning") as mock_logger:
                # Exercise - should re-raise exception as there is no fallback
                with pytest.raises(RefreshFailedError):
                    await service._get_oauth_token(record, provider="github", connection="default")

                # 1. Warning still emitted even without fallback
                mock_logger.assert_called_once()
                log_msg = mock_logger.call_args[0][0]
                assert "Warning: token refresh failed for github/default" in log_msg
                assert "token expired" in log_msg

                # 2. Audit written
                lines = audit_log.read_text().splitlines()
                assert len(lines) == 1
                entry = json.loads(lines[0])
                assert entry["event"] == "refresh_failed"
                assert entry["fallback_available"] is False


def test_auth_service_requires_explicit_identity() -> None:
    mock_vault = mock.AsyncMock()
    with pytest.raises(ValueError, match="explicit identity"):
        AuthService(mock_vault, identity="")


def test_auth_service_scopes_collection_by_vault_id() -> None:
    mock_vault = mock.AsyncMock()
    service = AuthService(
        mock_vault,
        identity="agent-a",
        principal_id="principal_1",
        vault_id="vault_default",
    )
    assert service._coll == "vault:vault_default"
