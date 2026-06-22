"""Tests for CredentialService business logic."""

from datetime import timedelta
from unittest import mock

import pytest
import pytest_asyncio
from pydantic import ValidationError

from authsome.auth.models.connection import ConnectionRecord, ProviderMetadataRecord
from authsome.auth.models.enums import AuthType, ConnectionStatus, FlowType
from authsome.auth.models.provider import OAuthConfig, ProviderDefinition
from authsome.errors import (
    ConnectionNotFoundError,
    InvalidConnectionNameError,
    OperationNotAllowedError,
    RefreshFailedError,
)
from authsome.identity.principal import PrincipalRole
from authsome.server.credential_repository import CredentialRepository
from authsome.server.credential_service import CredentialService, validate_login_connection_name
from authsome.server.dependencies import create_vault
from authsome.server.schemas import CredentialResolutionResponse, GlobalProviderConnectionRecord
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


class StaticProviders:
    async def get(self, name: str):  # noqa: ANN001, ANN201
        return ProviderDefinition(
            name=name,
            display_name=name.title(),
            auth_type=AuthType.OAUTH2,
            flow=FlowType.PKCE,
            oauth=OAuthConfig(
                authorization_url="https://example.test/oauth",
                token_url="https://example.test/token",
                scopes=[],
            ),
        )

    async def list(self):  # noqa: ANN201
        return [await self.get("github")]

    async def list_by_source(self):  # noqa: ANN201
        return {"bundled": [await self.get("github")], "custom": []}

    async def save_custom(self, definition, *, force: bool = False) -> None:  # noqa: ANN001
        raise AssertionError("unexpected provider save")

    async def delete_custom(self, name: str) -> bool:
        return False

    async def is_custom(self, name: str) -> bool:
        return False


class MemoryGlobalConnections:
    def __init__(self) -> None:
        self.pointer: GlobalProviderConnectionRecord | None = None

    async def get(self, provider: str) -> GlobalProviderConnectionRecord | None:
        if self.pointer is None or self.pointer.provider != provider:
            return None
        return self.pointer

    async def upsert(self, record: GlobalProviderConnectionRecord) -> GlobalProviderConnectionRecord:
        self.pointer = record
        return record

    async def delete(self, provider: str) -> bool:
        if self.pointer is None or self.pointer.provider != provider:
            return False
        self.pointer = None
        return True

    async def delete_if_target(
        self,
        provider: str,
        owner_vault_id: str,
        connection_name: str,
        *,
        updated_at=None,  # noqa: ANN001
    ) -> bool:
        if (
            self.pointer is None
            or self.pointer.provider != provider
            or self.pointer.owner_vault_id != owner_vault_id
            or self.pointer.connection_name != connection_name
            or (updated_at is not None and self.pointer.updated_at != updated_at)
        ):
            return False
        self.pointer = None
        return True


class SwappingMemoryGlobalConnections(MemoryGlobalConnections):
    def __init__(
        self,
        *,
        initial_pointer: GlobalProviderConnectionRecord,
        replacement_pointer: GlobalProviderConnectionRecord,
    ) -> None:
        super().__init__()
        self.pointer = initial_pointer
        self._replacement_pointer = replacement_pointer
        self._swapped = False

    async def get(self, provider: str) -> GlobalProviderConnectionRecord | None:
        pointer = await super().get(provider)
        if pointer is not None and not self._swapped:
            self.pointer = self._replacement_pointer
            self._swapped = True
            return pointer
        return pointer


def _credentials(
    vault, *, identity: str | None = "agent-a", principal_id: str | None = None, vault_id: str = "vault_default"
):  # noqa: ANN001
    return CredentialRepository(vault, identity=identity, principal_id=principal_id, vault_id=vault_id)


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
            await log.async_shutdown()
            await store.close()

    @pytest.fixture
    def service(self) -> CredentialService:
        mock_vault = mock.AsyncMock()
        return CredentialService(
            credentials=_credentials(mock_vault, identity="test-profile", vault_id="test-vault"),
            providers=EmptyProviders(),
            global_connections=mock.AsyncMock(),
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

        with (
            mock.patch.object(service, "_refresh_token", side_effect=RefreshFailedError("API down", provider="github")),
            mock.patch("loguru.logger.warning") as mock_logger,
        ):
            # Exercise
            token = await service._get_oauth_token_with_credentials(
                record,
                "github",
                "default",
                service._credentials,
                refresh_with_credentials=False,
            )

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

        with (
            mock.patch.object(
                service, "_refresh_token", side_effect=RefreshFailedError("API rejected", provider="github")
            ),
            mock.patch("loguru.logger.warning") as mock_logger,
        ):
            # Exercise - should re-raise exception as there is no fallback
            with pytest.raises(RefreshFailedError):
                await service._get_oauth_token_with_credentials(
                    record,
                    "github",
                    "default",
                    service._credentials,
                    refresh_with_credentials=False,
                )

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
        global_connections=mock.AsyncMock(),
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
        global_connections=mock.AsyncMock(),
        identity="agent-a",
        principal_id="principal_1",
        vault_id="vault_default",
    )
    assert service._credentials.collection == "vault:vault_default"


def test_auth_service_exposes_global_connection_registry() -> None:
    mock_vault = mock.AsyncMock()
    global_connections = mock.AsyncMock()
    service = CredentialService(
        credentials=_credentials(mock_vault, identity="agent-a", principal_id="principal_1"),
        providers=EmptyProviders(),
        global_connections=global_connections,
        identity="agent-a",
        principal_id="principal_1",
        vault_id="vault_default",
    )

    assert service.global_connections is global_connections


def test_auth_service_requires_providers() -> None:
    mock_vault = mock.AsyncMock()

    with pytest.raises(TypeError):
        CredentialService(
            credentials=_credentials(mock_vault, identity="agent-a"),
            global_connections=mock.AsyncMock(),
            identity="agent-a",
            vault_id="vault_default",
        )  # type: ignore[call-arg]


@pytest.mark.asyncio
async def test_resolve_credentials_uses_local_default_before_global(tmp_path) -> None:  # noqa: ANN001
    vault = await create_vault(tmp_path)
    global_connections = MemoryGlobalConnections()
    service = CredentialService(
        credentials=_credentials(vault, identity="agent-a", principal_id="principal_1", vault_id="vault_user"),
        providers=StaticProviders(),
        global_connections=global_connections,
        identity="agent-a",
        principal_id="principal_1",
        vault_id="vault_user",
    )
    owner_credentials = _credentials(
        vault,
        identity="agent-admin",
        principal_id="principal_admin",
        vault_id="vault_admin",
    )

    await service._credentials.save_connection(
        ConnectionRecord(
            provider="github",
            identity="agent-a",
            principal_id="principal_1",
            vault_id="vault_user",
            connection_name="default",
            auth_type=AuthType.OAUTH2,
            status=ConnectionStatus.CONNECTED,
            access_token="local-token",
        )
    )
    await owner_credentials.save_connection(
        ConnectionRecord(
            provider="github",
            identity="agent-admin",
            principal_id="principal_admin",
            vault_id="vault_admin",
            connection_name="shared",
            auth_type=AuthType.OAUTH2,
            status=ConnectionStatus.CONNECTED,
            access_token="global-token",
        )
    )
    await global_connections.upsert(
        GlobalProviderConnectionRecord(
            provider="github",
            owner_principal_id="principal_admin",
            owner_vault_id="vault_admin",
            connection_name="shared",
            created_by_identity="agent-admin",
        )
    )

    resolved = await service.resolve_credentials(provider="github")

    assert resolved["headers"] == {"Authorization": "Bearer local-token"}
    assert resolved["source"] == "local"


@pytest.mark.asyncio
async def test_resolve_credentials_falls_back_to_global_for_missing_default(tmp_path) -> None:  # noqa: ANN001
    vault = await create_vault(tmp_path)
    global_connections = MemoryGlobalConnections()
    service = CredentialService(
        credentials=_credentials(vault, identity="agent-a", principal_id="principal_1", vault_id="vault_user"),
        providers=StaticProviders(),
        global_connections=global_connections,
        identity="agent-a",
        principal_id="principal_1",
        vault_id="vault_user",
    )
    owner_service = service._for_vault("vault_admin")

    await owner_service._credentials.save_connection(
        ConnectionRecord(
            provider="github",
            identity="agent-a",
            principal_id="principal_1",
            vault_id="vault_admin",
            connection_name="shared",
            auth_type=AuthType.OAUTH2,
            status=ConnectionStatus.CONNECTED,
            access_token="global-token",
        )
    )
    await global_connections.upsert(
        GlobalProviderConnectionRecord(
            provider="github",
            owner_principal_id="principal_admin",
            owner_vault_id="vault_admin",
            connection_name="shared",
            created_by_identity="agent-admin",
        )
    )

    resolved = await service.resolve_credentials(provider="github")

    assert resolved["headers"] == {"Authorization": "Bearer global-token"}
    assert resolved["source"] == "global"

    response = CredentialResolutionResponse.model_validate(resolved)

    assert response.source == "global"


def test_credential_resolution_response_requires_source() -> None:
    with pytest.raises(ValidationError):
        CredentialResolutionResponse.model_validate(
            {
                "provider": "github",
                "connection": "shared",
                "headers": {"Authorization": "Bearer token"},
                "expires_at": None,
            }
        )


@pytest.mark.asyncio
async def test_named_missing_connection_does_not_fall_back_to_global(tmp_path) -> None:  # noqa: ANN001
    vault = await create_vault(tmp_path)
    global_connections = MemoryGlobalConnections()
    service = CredentialService(
        credentials=_credentials(vault, identity="agent-a", principal_id="principal_1", vault_id="vault_user"),
        providers=StaticProviders(),
        global_connections=global_connections,
        identity="agent-a",
        principal_id="principal_1",
        vault_id="vault_user",
    )
    owner_service = service._for_vault("vault_admin")

    await owner_service._credentials.save_connection(
        ConnectionRecord(
            provider="github",
            identity="agent-a",
            principal_id="principal_1",
            vault_id="vault_admin",
            connection_name="shared",
            auth_type=AuthType.OAUTH2,
            status=ConnectionStatus.CONNECTED,
            access_token="global-token",
        )
    )
    await global_connections.upsert(
        GlobalProviderConnectionRecord(
            provider="github",
            owner_principal_id="principal_admin",
            owner_vault_id="vault_admin",
            connection_name="shared",
            created_by_identity="agent-admin",
        )
    )

    with pytest.raises(ConnectionNotFoundError):
        await service.resolve_credentials(provider="github", connection="work")


@pytest.mark.asyncio
async def test_resolve_credentials_global_refresh_writes_state_to_owner_vault(tmp_path) -> None:  # noqa: ANN001
    vault = await create_vault(tmp_path)
    global_connections = MemoryGlobalConnections()
    service = CredentialService(
        credentials=_credentials(vault, identity="agent-a", principal_id="principal_1", vault_id="vault_user"),
        providers=StaticProviders(),
        global_connections=global_connections,
        identity="agent-a",
        principal_id="principal_1",
        vault_id="vault_user",
    )
    owner_credentials = _credentials(
        vault,
        identity="agent-admin",
        principal_id="principal_admin",
        vault_id="vault_admin",
    )
    expires_at = utc_now() + timedelta(seconds=1)

    await owner_credentials.save_connection(
        ConnectionRecord(
            provider="github",
            identity="agent-admin",
            principal_id="principal_admin",
            vault_id="vault_admin",
            connection_name="shared",
            auth_type=AuthType.OAUTH2,
            status=ConnectionStatus.CONNECTED,
            access_token="stale-token",
            refresh_token="refresh-token",
            expires_at=expires_at,
        )
    )
    await global_connections.upsert(
        GlobalProviderConnectionRecord(
            provider="github",
            owner_principal_id="principal_admin",
            owner_vault_id="vault_admin",
            connection_name="shared",
            created_by_identity="agent-admin",
        )
    )
    captured_vault_ids: list[str] = []

    class FakePkceFlow:
        def refresh(self, *, provider, record, client_id=None, client_secret=None):  # noqa: ANN001, ANN201
            del provider, client_id, client_secret
            return record.model_copy(
                update={
                    "access_token": "fresh-token",
                    "expires_at": utc_now() + timedelta(hours=1),
                }
            )

    original_refresh = CredentialService._refresh_token_with_credentials

    async def recording_refresh(self, record, provider_name, credentials):  # noqa: ANN001, ANN201
        captured_vault_ids.append(credentials.vault_id)
        return await original_refresh(self, record, provider_name, credentials)

    with (
        mock.patch.dict("authsome.server.credential_service._FLOW_HANDLERS", {FlowType.PKCE: FakePkceFlow}),
        mock.patch.object(CredentialService, "_refresh_token_with_credentials", recording_refresh),
    ):
        resolved = await service.resolve_credentials(provider="github")

    owner_state = await owner_credentials.get_provider_state("github")
    user_state = await service._credentials.get_provider_state("github")
    owner_connection = await owner_credentials.get_connection("github", "shared")

    assert resolved["headers"] == {"Authorization": "Bearer fresh-token"}
    assert captured_vault_ids == ["vault_admin"]
    assert owner_state is not None
    assert owner_state.vault_id == "vault_admin"
    assert user_state is None
    assert owner_connection is not None
    assert owner_connection.access_token == "fresh-token"
    assert owner_connection.identity == "agent-admin"
    assert owner_connection.principal_id == "principal_admin"
    assert owner_state.identity == "agent-admin"
    assert owner_state.principal_id == "principal_admin"


@pytest.mark.asyncio
async def test_admin_can_make_own_connection_global(tmp_path) -> None:  # noqa: ANN001
    vault = await create_vault(tmp_path)
    global_connections = MemoryGlobalConnections()
    service = CredentialService(
        credentials=_credentials(vault, identity="agent-admin", principal_id="principal_admin", vault_id="vault_admin"),
        providers=StaticProviders(),
        global_connections=global_connections,
        identity="agent-admin",
        principal_id="principal_admin",
        principal_role=PrincipalRole.ADMIN,
        vault_id="vault_admin",
    )

    await service._credentials.save_connection(
        ConnectionRecord(
            provider="github",
            identity="agent-admin",
            principal_id="principal_admin",
            vault_id="vault_admin",
            connection_name="default",
            auth_type=AuthType.OAUTH2,
            status=ConnectionStatus.CONNECTED,
            access_token="admin-token",
        )
    )

    pointer = await service.set_global_connection("github", "default")

    assert pointer.provider == "github"
    assert pointer.owner_principal_id == "principal_admin"
    assert pointer.owner_vault_id == "vault_admin"
    assert pointer.connection_name == "default"
    assert global_connections.pointer == pointer


@pytest.mark.asyncio
async def test_set_global_connection_resolves_local_default_alias(tmp_path) -> None:  # noqa: ANN001
    vault = await create_vault(tmp_path)
    global_connections = MemoryGlobalConnections()
    service = CredentialService(
        credentials=_credentials(vault, identity="agent-admin", principal_id="principal_admin", vault_id="vault_admin"),
        providers=StaticProviders(),
        global_connections=global_connections,
        identity="agent-admin",
        principal_id="principal_admin",
        principal_role=PrincipalRole.ADMIN,
        vault_id="vault_admin",
    )

    await service._credentials.save_connection(
        ConnectionRecord(
            provider="github",
            identity="agent-admin",
            principal_id="principal_admin",
            vault_id="vault_admin",
            connection_name="work",
            auth_type=AuthType.OAUTH2,
            status=ConnectionStatus.CONNECTED,
            access_token="admin-token",
        )
    )
    await service._credentials.save_provider_metadata(
        ProviderMetadataRecord(
            provider="github",
            principal_id="principal_admin",
            vault_id="vault_admin",
            default_connection="work",
            connection_names=["work"],
        )
    )

    pointer = await service.set_global_connection("github", "default")

    assert pointer.connection_name == "work"
    assert global_connections.pointer == pointer


@pytest.mark.asyncio
async def test_non_admin_cannot_make_connection_global(tmp_path) -> None:  # noqa: ANN001
    vault = await create_vault(tmp_path)
    service = CredentialService(
        credentials=_credentials(vault, identity="agent-user", principal_id="principal_user", vault_id="vault_user"),
        providers=StaticProviders(),
        global_connections=MemoryGlobalConnections(),
        identity="agent-user",
        principal_id="principal_user",
        principal_role=PrincipalRole.USER,
        vault_id="vault_user",
    )

    with pytest.raises(OperationNotAllowedError):
        await service.set_global_connection("github", "default")


@pytest.mark.asyncio
async def test_admin_can_unset_global_connection(tmp_path) -> None:  # noqa: ANN001
    vault = await create_vault(tmp_path)
    global_connections = MemoryGlobalConnections()
    service = CredentialService(
        credentials=_credentials(vault, identity="agent-admin", principal_id="principal_admin", vault_id="vault_admin"),
        providers=StaticProviders(),
        global_connections=global_connections,
        identity="agent-admin",
        principal_id="principal_admin",
        principal_role=PrincipalRole.ADMIN,
        vault_id="vault_admin",
    )
    global_connections.pointer = GlobalProviderConnectionRecord(
        provider="github",
        owner_principal_id="someone-else",
        owner_vault_id="vault_elsewhere",
        connection_name="shared",
        created_by_identity="agent-other",
    )

    deleted = await service.unset_global_connection("github")

    assert deleted is True
    assert global_connections.pointer is None


@pytest.mark.asyncio
async def test_cross_admin_unset_global_connection_audits_removed_target_fields(tmp_path) -> None:  # noqa: ANN001
    vault = await create_vault(tmp_path)
    global_connections = MemoryGlobalConnections()
    service = CredentialService(
        credentials=_credentials(vault, identity="agent-admin", principal_id="principal_admin", vault_id="vault_admin"),
        providers=StaticProviders(),
        global_connections=global_connections,
        identity="agent-admin",
        principal_id="principal_admin",
        principal_role=PrincipalRole.ADMIN,
        vault_id="vault_admin",
    )
    global_connections.pointer = GlobalProviderConnectionRecord(
        provider="github",
        owner_principal_id="principal_owner",
        owner_vault_id="vault_owner",
        connection_name="shared",
        created_by_identity="agent-owner",
    )

    with mock.patch("authsome.server.credential_service.audit.emit_event") as emit_event:
        deleted = await service.unset_global_connection("github")

    assert deleted is True
    emit_event.assert_called_once_with(
        "provider.global_connection_unset",
        provider="github",
        identity="agent-admin",
        principal_id="principal_admin",
        owner_principal_id="principal_owner",
        owner_vault_id="vault_owner",
        connection="shared",
        status="success",
        deleted=True,
    )


@pytest.mark.asyncio
async def test_unset_global_connection_does_not_delete_repointed_pointer(tmp_path) -> None:  # noqa: ANN001
    vault = await create_vault(tmp_path)
    initial_pointer = GlobalProviderConnectionRecord(
        provider="github",
        owner_principal_id="principal_old",
        owner_vault_id="vault_old",
        connection_name="shared-old",
        created_by_identity="agent-old",
    )
    replacement_pointer = GlobalProviderConnectionRecord(
        provider="github",
        owner_principal_id="principal_new",
        owner_vault_id="vault_new",
        connection_name="shared-new",
        created_by_identity="agent-new",
    )
    global_connections = SwappingMemoryGlobalConnections(
        initial_pointer=initial_pointer,
        replacement_pointer=replacement_pointer,
    )
    service = CredentialService(
        credentials=_credentials(vault, identity="agent-admin", principal_id="principal_admin", vault_id="vault_admin"),
        providers=StaticProviders(),
        global_connections=global_connections,
        identity="agent-admin",
        principal_id="principal_admin",
        principal_role=PrincipalRole.ADMIN,
        vault_id="vault_admin",
    )

    with mock.patch("authsome.server.credential_service.audit.emit_event") as emit_event:
        deleted = await service.unset_global_connection("github")

    assert deleted is False
    assert global_connections.pointer == replacement_pointer
    emit_event.assert_called_once_with(
        "provider.global_connection_unset",
        provider="github",
        identity="agent-admin",
        principal_id="principal_admin",
        owner_principal_id=None,
        owner_vault_id=None,
        connection=None,
        status="success",
        deleted=False,
    )


@pytest.mark.asyncio
async def test_unset_global_connection_does_not_delete_reset_same_target_pointer(tmp_path) -> None:  # noqa: ANN001
    vault = await create_vault(tmp_path)
    first_updated_at = utc_now()
    second_updated_at = first_updated_at + timedelta(seconds=1)
    initial_pointer = GlobalProviderConnectionRecord(
        provider="github",
        owner_principal_id="principal_owner",
        owner_vault_id="vault_owner",
        connection_name="shared",
        created_by_identity="agent-owner",
        updated_at=first_updated_at,
    )
    replacement_pointer = initial_pointer.model_copy(update={"updated_at": second_updated_at})
    global_connections = SwappingMemoryGlobalConnections(
        initial_pointer=initial_pointer,
        replacement_pointer=replacement_pointer,
    )
    service = CredentialService(
        credentials=_credentials(vault, identity="agent-admin", principal_id="principal_admin", vault_id="vault_admin"),
        providers=StaticProviders(),
        global_connections=global_connections,
        identity="agent-admin",
        principal_id="principal_admin",
        principal_role=PrincipalRole.ADMIN,
        vault_id="vault_admin",
    )

    with mock.patch("authsome.server.credential_service.audit.emit_event") as emit_event:
        deleted = await service.unset_global_connection("github")

    assert deleted is False
    assert global_connections.pointer == replacement_pointer
    emit_event.assert_called_once_with(
        "provider.global_connection_unset",
        provider="github",
        identity="agent-admin",
        principal_id="principal_admin",
        owner_principal_id=None,
        owner_vault_id=None,
        connection=None,
        status="success",
        deleted=False,
    )


@pytest.mark.asyncio
async def test_logout_of_global_target_removes_pointer(tmp_path) -> None:  # noqa: ANN001
    vault = await create_vault(tmp_path)
    global_connections = MemoryGlobalConnections()
    service = CredentialService(
        credentials=_credentials(vault, identity="agent-admin", principal_id="principal_admin", vault_id="vault_admin"),
        providers=StaticProviders(),
        global_connections=global_connections,
        identity="agent-admin",
        principal_id="principal_admin",
        principal_role=PrincipalRole.ADMIN,
        vault_id="vault_admin",
    )

    await service._credentials.save_connection(
        ConnectionRecord(
            provider="github",
            identity="agent-admin",
            principal_id="principal_admin",
            vault_id="vault_admin",
            connection_name="default",
            auth_type=AuthType.OAUTH2,
            status=ConnectionStatus.CONNECTED,
            access_token="admin-token",
        )
    )
    await service.set_global_connection("github", "default")

    await service.logout("github", "default")

    assert global_connections.pointer is None


@pytest.mark.asyncio
async def test_logout_of_other_local_connection_keeps_pointer(tmp_path) -> None:  # noqa: ANN001
    vault = await create_vault(tmp_path)
    global_connections = MemoryGlobalConnections()
    service = CredentialService(
        credentials=_credentials(vault, identity="agent-admin", principal_id="principal_admin", vault_id="vault_admin"),
        providers=StaticProviders(),
        global_connections=global_connections,
        identity="agent-admin",
        principal_id="principal_admin",
        principal_role=PrincipalRole.ADMIN,
        vault_id="vault_admin",
    )

    await service._credentials.save_connection(
        ConnectionRecord(
            provider="github",
            identity="agent-admin",
            principal_id="principal_admin",
            vault_id="vault_admin",
            connection_name="default",
            auth_type=AuthType.OAUTH2,
            status=ConnectionStatus.CONNECTED,
            access_token="admin-token",
        )
    )
    await service._credentials.save_connection(
        ConnectionRecord(
            provider="github",
            identity="agent-admin",
            principal_id="principal_admin",
            vault_id="vault_admin",
            connection_name="other",
            auth_type=AuthType.OAUTH2,
            status=ConnectionStatus.CONNECTED,
            access_token="other-token",
        )
    )
    await service.set_global_connection("github", "default")

    await service.logout("github", "other")

    assert global_connections.pointer is not None
    assert global_connections.pointer.connection_name == "default"


def _named_first_service(vault) -> CredentialService:  # noqa: ANN001
    return CredentialService(
        credentials=_credentials(vault, identity="agent-a", principal_id="principal_1", vault_id="vault_user"),
        providers=StaticProviders(),
        global_connections=MemoryGlobalConnections(),
        identity="agent-a",
        principal_id="principal_1",
        vault_id="vault_user",
    )


async def _save_named_connection(service: CredentialService, name: str) -> None:
    await service._credentials.save_connection(
        ConnectionRecord(
            provider="github",
            identity="agent-a",
            principal_id="principal_1",
            vault_id="vault_user",
            connection_name=name,
            auth_type=AuthType.OAUTH2,
            status=ConnectionStatus.CONNECTED,
            access_token=f"token-{name}",
        )
    )
    await service._update_provider_metadata("github", name)


@pytest.mark.asyncio
async def test_first_connection_becomes_default(tmp_path) -> None:  # noqa: ANN001
    vault = await create_vault(tmp_path)
    service = _named_first_service(vault)

    await _save_named_connection(service, "work")

    metadata = await service._credentials.get_provider_metadata("github")
    assert metadata is not None
    assert metadata.default_connection == "work"


@pytest.mark.asyncio
async def test_second_connection_leaves_default_unchanged(tmp_path) -> None:  # noqa: ANN001
    vault = await create_vault(tmp_path)
    service = _named_first_service(vault)

    await _save_named_connection(service, "work")
    await _save_named_connection(service, "personal")

    metadata = await service._credentials.get_provider_metadata("github")
    assert metadata is not None
    assert metadata.default_connection == "work"
    assert set(metadata.connection_names) == {"work", "personal"}


@pytest.mark.asyncio
async def test_resolve_connection_name_uses_metadata_default(tmp_path) -> None:  # noqa: ANN001
    vault = await create_vault(tmp_path)
    service = _named_first_service(vault)
    await _save_named_connection(service, "work")

    # Both an omitted name and the reserved "default" alias resolve to the
    # provider's metadata default — no record literally named "default" exists.
    assert await service.resolve_connection_name("github", None) == "work"
    assert await service.resolve_connection_name("github", "default") == "work"
    assert await service.resolve_connection_name("github", "personal") == "personal"


@pytest.mark.asyncio
async def test_omitted_connection_resolves_to_default_record(tmp_path) -> None:  # noqa: ANN001
    vault = await create_vault(tmp_path)
    service = _named_first_service(vault)
    await _save_named_connection(service, "work")

    record = await service.get_connection("github")
    assert record.connection_name == "work"


@pytest.mark.asyncio
async def test_legacy_default_record_still_resolves(tmp_path) -> None:  # noqa: ANN001
    vault = await create_vault(tmp_path)
    service = _named_first_service(vault)

    # Simulate a pre-existing vault whose metadata predates named-first
    # connections: a literal "default" record plus matching metadata.
    await _save_named_connection(service, "default")

    metadata = await service._credentials.get_provider_metadata("github")
    assert metadata is not None and metadata.default_connection == "default"
    record = await service.get_connection("github")
    assert record.connection_name == "default"


def test_validate_login_connection_name_rejects_reserved_and_empty() -> None:
    assert validate_login_connection_name("  work ", provider="github") == "work"
    with pytest.raises(InvalidConnectionNameError):
        validate_login_connection_name("", provider="github")
    with pytest.raises(InvalidConnectionNameError):
        validate_login_connection_name("   ", provider="github")
    with pytest.raises(InvalidConnectionNameError):
        validate_login_connection_name("default", provider="github")
