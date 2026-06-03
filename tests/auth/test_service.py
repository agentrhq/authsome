"""Tests for CredentialService business logic."""

from datetime import timedelta
from unittest import mock

import pytest
import pytest_asyncio

from authsome.auth.models.connection import ConnectionRecord
from authsome.auth.models.enums import AuthType, ConnectionStatus
from authsome.errors import RefreshFailedError
from authsome.server.credential_repository import CredentialRepository
from authsome.server.credential_service import CredentialService
from authsome.server.store import create_server_store
from authsome.server.store.repositories import ServerAuditLog
from authsome.utils import utc_now


class EmptyProviders:
    async def get(self, name: str):  # noqa: ANN001, ANN201
        from authsome.errors import ProviderNotFoundError

        raise ProviderNotFoundError(name)

    async def list(self):  # noqa: ANN201
        return []

    async def list_by_source(self):  # noqa: ANN201
        return {"bundled": [], "custom": []}

    async def save_custom(self, definition, *, force: bool = False) -> None:  # noqa: ANN001
        raise AssertionError("unexpected provider save")

    async def delete_custom(self, name: str) -> bool:
        return False


def _credentials(
    vault, *, identity: str | None = "agent-a", principal_id: str | None = None, vault_id: str = "vault_default"
):  # noqa: ANN001
    return CredentialRepository(vault, identity=identity, principal_id=principal_id, vault_id=vault_id)

    async def is_custom(self, name: str) -> bool:
        return False


@pytest.mark.asyncio
class TestAuthServiceRefreshLogs:
    """Tests validating that token refresh failure writes correct logs and audit trails."""

    @pytest_asyncio.fixture
    async def audit_log(self, tmp_path) -> ServerAuditLog:  # noqa: ANN001
        store = await create_server_store(home=tmp_path)
        log = store.audit_events.configure_exporter()
        try:
            yield log
        finally:
            log.shutdown()
            await store.close()

    @pytest.fixture
    def service(self) -> CredentialService:
        mock_vault = mock.AsyncMock()
        return CredentialService(
            credentials=_credentials(mock_vault, identity="test-profile", vault_id="test-vault"),
            providers=EmptyProviders(),
            identity="test-profile",
            vault_id="test-vault",
        )

    async def test_refresh_failure_fallback_available(self, audit_log: ServerAuditLog, service: CredentialService):
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
                entries = await audit_log.list_events()
                assert len(entries) == 1
                entry = entries[0]
                assert entry["event"] == "provider.refresh_failed"
                assert entry["fallback_available"] is True
                assert "API down" in entry["error"]

    async def test_refresh_failure_expired(self, audit_log: ServerAuditLog, service: CredentialService):
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
                entries = await audit_log.list_events()
                assert len(entries) == 1
                entry = entries[0]
                assert entry["event"] == "provider.refresh_failed"
                assert entry["fallback_available"] is False


def test_auth_service_allows_missing_identity() -> None:
    mock_vault = mock.AsyncMock()
    service = CredentialService(
        credentials=_credentials(mock_vault, identity=None, principal_id="principal_1"),
        providers=EmptyProviders(),
        identity=None,
        principal_id="principal_1",
        vault_id="vault_default",
    )
    assert service.identity is None


def test_auth_service_scopes_collection_by_vault_id() -> None:
    mock_vault = mock.AsyncMock()
    service = CredentialService(
        credentials=_credentials(mock_vault, identity="agent-a", principal_id="principal_1"),
        providers=EmptyProviders(),
        identity="agent-a",
        principal_id="principal_1",
        vault_id="vault_default",
    )
    assert service._credentials.collection == "vault:vault_default"


def test_auth_service_requires_providers() -> None:
    mock_vault = mock.AsyncMock()

    with pytest.raises(TypeError):
        CredentialService(
            credentials=_credentials(mock_vault, identity="agent-a"),
            identity="agent-a",
            vault_id="vault_default",
        )  # type: ignore[call-arg]
