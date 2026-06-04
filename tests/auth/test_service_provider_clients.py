"""Focused tests for server-scoped provider client storage."""

from unittest import mock

import pytest

from authsome.auth.flows.base import FlowResult
from authsome.auth.models.connection import ConnectionRecord, ProviderClientRecord, ProviderMetadataRecord
from authsome.auth.models.enums import AuthType, ConnectionStatus, FlowType
from authsome.auth.models.provider import OAuthConfig, ProviderDefinition
from authsome.auth.sessions import AuthSession
from authsome.cli.identity import create_identity
from authsome.errors import OperationNotAllowedError
from authsome.identity.principal import PrincipalRole
from authsome.server.credential_repository import CredentialRepository, build_store_key
from authsome.server.credential_service import CredentialService
from authsome.server.dependencies import (
    create_store,
    create_vault,
)
from authsome.server.provider_repository import ProviderRepository


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

    async def is_custom(self, name: str) -> bool:
        return False


def _service(vault, **kwargs) -> CredentialService:  # noqa: ANN001, ANN003
    identity = kwargs.get("identity")
    principal_id = kwargs.get("principal_id")
    vault_id = kwargs.get("vault_id", "vault_default")
    credentials = CredentialRepository(vault, identity=identity, principal_id=principal_id, vault_id=vault_id)
    return CredentialService(credentials=credentials, providers=EmptyProviders(), **kwargs)


def _make_provider(*, flow: FlowType = FlowType.PKCE) -> ProviderDefinition:
    return ProviderDefinition(
        name="github",
        display_name="GitHub",
        auth_type=AuthType.OAUTH2,
        flow=flow,
        oauth=OAuthConfig(
            authorization_url="https://github.com/login/oauth/authorize",
            token_url="https://github.com/login/oauth/access_token",
            scopes=["repo"],
        ),
    )


def _make_session(*, flow_type: FlowType) -> AuthSession:
    return AuthSession(
        session_id="sess_123",
        provider="github",
        identity="steady-wisely-boldly-0042",
        connection_name="default",
        flow_type=flow_type.value,
    )


@pytest.mark.asyncio
async def test_get_provider_client_reads_from_server_scope() -> None:
    vault = mock.AsyncMock()
    vault.get.return_value = ProviderClientRecord(provider="github", client_id="cid").model_dump_json()
    service = _service(vault, identity="steady-wisely-boldly-0042")

    record = await service.get_provider_client("github")

    assert record is not None
    assert record.client_id == "cid"
    vault.get.assert_awaited_once_with("server:provider:github:client", collection="server")


@pytest.mark.asyncio
async def test_save_inputs_persists_provider_client_to_server_scope() -> None:
    vault = mock.AsyncMock()
    vault.get.return_value = None
    service = _service(vault, identity="steady-wisely-boldly-0042", principal_role=PrincipalRole.ADMIN)
    session = _make_session(flow_type=FlowType.PKCE)

    await service.save_inputs(
        session,
        {"client_id": "cid", "client_secret": "secret", "scopes": "repo,read:user"},
    )

    vault.put.assert_awaited_once()
    put_call = vault.put.await_args
    saved = ProviderClientRecord.model_validate_json(put_call.args[1])

    assert put_call.args[0] == "server:provider:github:client"
    assert put_call.kwargs["collection"] == "server"
    assert saved.provider == "github"
    assert saved.client_id == "cid"
    assert saved.client_secret == "secret"
    assert saved.scopes == ["repo", "read:user"]
    assert "identity" not in saved.model_dump(mode="json")
    assert "requested_scopes" not in session.payload


@pytest.mark.asyncio
async def test_save_inputs_with_scopes_only_writes_server_record() -> None:
    vault = mock.AsyncMock()
    vault.get.return_value = None
    service = _service(vault, identity="steady-wisely-boldly-0042", principal_role=PrincipalRole.ADMIN)
    session = _make_session(flow_type=FlowType.PKCE)

    await service.save_inputs(session, {"scopes": "repo,read:user"})

    vault.put.assert_awaited_once()
    put_call = vault.put.await_args
    saved = ProviderClientRecord.model_validate_json(put_call.args[1])
    assert saved.scopes == ["repo", "read:user"]


@pytest.mark.asyncio
async def test_get_required_inputs_skips_scope_prompt_when_server_scopes_exist() -> None:
    vault = mock.AsyncMock()
    service = _service(vault, identity="second-identity")
    session = _make_session(flow_type=FlowType.PKCE)

    with (
        mock.patch.object(
            service._credentials,
            "get_provider_client",
            new=mock.AsyncMock(
                return_value=ProviderClientRecord(
                    provider="github",
                    client_id="cid",
                    scopes=["repo", "read:user"],
                )
            ),
        ),
        mock.patch.object(service, "get_provider", new=mock.AsyncMock(return_value=_make_provider())),
    ):
        fields = await service.get_required_inputs(session)

    assert all(field.name != "scopes" for field in fields)


@pytest.mark.asyncio
async def test_pkce_client_credentials_prompt_id_then_secret() -> None:
    vault = mock.AsyncMock()
    vault.get.return_value = None
    service = _service(vault, identity="steady-wisely-boldly-0042")
    session = _make_session(flow_type=FlowType.PKCE)

    with mock.patch.object(service, "get_provider", new=mock.AsyncMock(return_value=_make_provider())):
        fields = await service.get_required_inputs(session)

    credential_fields = [field for field in fields if field.name in {"client_id", "client_secret"}]
    assert [field.name for field in credential_fields] == ["client_id", "client_secret"]
    assert credential_fields[1].label == "Client Secret"


@pytest.mark.asyncio
async def test_update_provider_configuration_persists_default_scopes_when_omitted() -> None:
    vault = mock.AsyncMock()
    vault.get.return_value = None
    service = _service(vault, identity="steady-wisely-boldly-0042", principal_role=PrincipalRole.ADMIN)

    with mock.patch.object(service, "get_provider", new=mock.AsyncMock(return_value=_make_provider())):
        changed = await service.update_provider_configuration(
            "github",
            {"client_id": "cid", "client_secret": "secret"},
        )

    assert changed is True
    vault.put.assert_awaited_once()
    saved = ProviderClientRecord.model_validate_json(vault.put.await_args.args[1])
    assert saved.client_id == "cid"
    assert saved.client_secret == "secret"
    assert saved.scopes == ["repo"]


@pytest.mark.asyncio
async def test_update_provider_configuration_persists_submitted_scopes() -> None:
    vault = mock.AsyncMock()
    vault.get.return_value = None
    service = _service(vault, identity="steady-wisely-boldly-0042", principal_role=PrincipalRole.ADMIN)

    with mock.patch.object(service, "get_provider", new=mock.AsyncMock(return_value=_make_provider())):
        changed = await service.update_provider_configuration(
            "github",
            {"client_id": "cid", "client_secret": "secret", "scopes": "repo,read:user"},
        )

    assert changed is True
    saved = ProviderClientRecord.model_validate_json(vault.put.await_args.args[1])
    assert saved.scopes == ["repo", "read:user"]


@pytest.mark.asyncio
async def test_admin_provider_config_satisfies_next_identity_login() -> None:
    store: dict[tuple[str, str], str] = {}
    vault = mock.AsyncMock()

    async def get_value(key: str, *, collection: str) -> str | None:
        return store.get((collection, key))

    async def put_value(key: str, value: str, *, collection: str) -> None:
        store[(collection, key)] = value

    vault.get.side_effect = get_value
    vault.put.side_effect = put_value
    admin_service = _service(
        vault,
        identity=None,
        principal_id="principal_admin",
        principal_role=PrincipalRole.ADMIN,
    )
    identity_service = _service(
        vault,
        identity="steady-wisely-boldly-0042",
        principal_id="principal_user",
    )
    provider = _make_provider()

    with mock.patch.object(admin_service, "get_provider", new=mock.AsyncMock(return_value=provider)):
        await admin_service.update_provider_configuration(
            "github",
            {"client_id": "cid", "client_secret": "secret"},
        )

    with mock.patch.object(identity_service, "get_provider", new=mock.AsyncMock(return_value=provider)):
        fields = await identity_service.get_required_inputs(_make_session(flow_type=FlowType.PKCE))

    assert fields == []


@pytest.mark.asyncio
async def test_begin_login_flow_reuses_server_scopes() -> None:
    vault = mock.AsyncMock()
    vault.get.return_value = ProviderClientRecord(
        provider="github",
        client_id="cid",
        client_secret="secret",
        scopes=["repo", "read:user"],
    ).model_dump_json()
    service = _service(vault, identity="second-identity")
    session = _make_session(flow_type=FlowType.PKCE)
    handler = mock.AsyncMock()

    handlers = {FlowType.PKCE: mock.Mock(return_value=handler)}
    with (
        mock.patch("authsome.server.credential_service._FLOW_HANDLERS", handlers),
        mock.patch.object(service, "get_provider", new=mock.AsyncMock(return_value=_make_provider())),
    ):
        await service.begin_login_flow(session)

    handler.begin.assert_awaited_once()
    assert handler.begin.await_args.kwargs["scopes"] == ["repo", "read:user"]


@pytest.mark.asyncio
async def test_resume_login_flow_saves_dcr_client_record_to_server_scope() -> None:
    vault = mock.AsyncMock()
    vault.get.return_value = None
    service = _service(vault, identity="steady-wisely-boldly-0042", principal_role=PrincipalRole.ADMIN)
    session = _make_session(flow_type=FlowType.DCR_PKCE)
    session.payload["base_url"] = "https://api.github.example"

    connection = ConnectionRecord(
        provider="github",
        identity="steady-wisely-boldly-0042",
        connection_name="default",
        auth_type=AuthType.OAUTH2,
        status=ConnectionStatus.CONNECTED,
        access_token="access-token",
    )
    handler = mock.AsyncMock()
    handler.resume.return_value = FlowResult(
        connection=connection,
        client_record=ProviderClientRecord(
            provider="github",
            client_id="cid",
            client_secret="secret",
            base_url="https://api.github.example",
        ),
    )

    dcr_handlers = {FlowType.DCR_PKCE: mock.Mock(return_value=handler)}
    with mock.patch("authsome.server.credential_service._FLOW_HANDLERS", dcr_handlers):
        provider = _make_provider(flow=FlowType.DCR_PKCE)
        with (
            mock.patch.object(service, "get_provider", new=mock.AsyncMock(return_value=provider)),
            mock.patch.object(service._credentials, "save_connection", new=mock.AsyncMock()),
            mock.patch.object(service, "_update_provider_metadata", new=mock.AsyncMock()),
        ):
            result = await service.resume_login_flow(session, {"code": "auth-code", "state": "oauth-state"})

    assert result is not None
    assert result.base_url == "https://api.github.example"
    vault.put.assert_awaited_once()
    put_call = vault.put.await_args
    saved = ProviderClientRecord.model_validate_json(put_call.args[1])

    assert put_call.args[0] == "server:provider:github:client"
    assert put_call.kwargs["collection"] == "server"
    assert saved.client_id == "cid"
    assert saved.client_secret == "secret"
    assert saved.base_url == "https://api.github.example"
    assert "identity" not in saved.model_dump(mode="json")


@pytest.mark.asyncio
async def test_non_admin_save_inputs_rejects_shared_client_mutation() -> None:
    vault = mock.AsyncMock()
    vault.get.return_value = None
    service = _service(vault, identity="steady-wisely-boldly-0042")
    session = _make_session(flow_type=FlowType.PKCE)

    with pytest.raises(OperationNotAllowedError):
        await service.save_inputs(
            session,
            {"client_id": "cid", "client_secret": "secret", "scopes": "repo,read:user"},
        )


@pytest.mark.asyncio
async def test_non_admin_save_inputs_rejects_scopes_only_server_write() -> None:
    vault = mock.AsyncMock()
    vault.get.return_value = None
    service = _service(vault, identity="steady-wisely-boldly-0042")
    session = _make_session(flow_type=FlowType.PKCE)

    with pytest.raises(OperationNotAllowedError):
        await service.save_inputs(session, {"scopes": "repo,read:user"})


@pytest.mark.asyncio
async def test_non_admin_resume_login_flow_rejects_dcr_client_persistence() -> None:
    vault = mock.AsyncMock()
    vault.get.return_value = None
    service = _service(vault, identity="steady-wisely-boldly-0042")
    session = _make_session(flow_type=FlowType.DCR_PKCE)

    connection = ConnectionRecord(
        provider="github",
        identity="steady-wisely-boldly-0042",
        connection_name="default",
        auth_type=AuthType.OAUTH2,
        status=ConnectionStatus.CONNECTED,
        access_token="access-token",
    )
    handler = mock.AsyncMock()
    handler.resume.return_value = FlowResult(
        connection=connection,
        client_record=ProviderClientRecord(
            provider="github",
            client_id="cid",
            client_secret="secret",
        ),
    )

    dcr_handlers = {FlowType.DCR_PKCE: mock.Mock(return_value=handler)}
    with mock.patch("authsome.server.credential_service._FLOW_HANDLERS", dcr_handlers):
        provider = _make_provider(flow=FlowType.DCR_PKCE)
        with (
            mock.patch.object(service, "get_provider", new=mock.AsyncMock(return_value=provider)),
            pytest.raises(OperationNotAllowedError),
        ):
            await service.resume_login_flow(session, {"code": "auth-code", "state": "oauth-state"})


@pytest.mark.asyncio
async def test_revoke_local_deletes_shared_client_and_all_identity_connections(tmp_path) -> None:
    first_identity = create_identity(tmp_path, "steady-wisely-boldly-0042")
    store = await create_store(tmp_path)
    await store.identity_registry.register(handle=first_identity.handle, did=first_identity.did)
    primary_vault = await store.vaults.create_default()
    secondary_vault = await store.vaults.create_default()

    vault = await create_vault(store.home)
    try:
        service = CredentialService(
            credentials=CredentialRepository(
                vault,
                identity="steady-wisely-boldly-0042",
                principal_id="principal_1",
                vault_id=primary_vault.vault_id,
            ),
            providers=ProviderRepository(store.provider_definitions),
            identity="steady-wisely-boldly-0042",
            principal_id="principal_1",
            principal_role=PrincipalRole.ADMIN,
            vault_id=primary_vault.vault_id,
        )

        primary_connection = ConnectionRecord(
            provider="github",
            identity="steady-wisely-boldly-0042",
            principal_id="principal_1",
            vault_id=primary_vault.vault_id,
            connection_name="default",
            auth_type=AuthType.OAUTH2,
            status=ConnectionStatus.CONNECTED,
        )
        secondary_connection = ConnectionRecord(
            provider="github",
            identity="rapid-brightly-firmly-0007",
            principal_id="principal_2",
            vault_id=secondary_vault.vault_id,
            connection_name="work",
            auth_type=AuthType.OAUTH2,
            status=ConnectionStatus.CONNECTED,
        )

        await vault.put(
            build_store_key(provider="github", record_type="server"),
            ProviderClientRecord(provider="github", client_id="cid").model_dump_json(),
            collection="server",
        )
        await vault.put(
            build_store_key(vault=primary_vault.vault_id, provider="github", record_type="metadata"),
            ProviderMetadataRecord(
                identity=primary_connection.identity,
                principal_id="principal_1",
                vault_id=primary_vault.vault_id,
                provider="github",
                connection_names=["default"],
                last_used_connection="default",
            ).model_dump_json(),
            collection=f"vault:{primary_vault.vault_id}",
        )
        await vault.put(
            build_store_key(
                vault=primary_vault.vault_id,
                provider="github",
                record_type="connection",
                connection=primary_connection.connection_name,
            ),
            primary_connection.model_dump_json(),
            collection=f"vault:{primary_vault.vault_id}",
        )
        await vault.put(
            build_store_key(vault=secondary_vault.vault_id, provider="github", record_type="metadata"),
            ProviderMetadataRecord(
                identity=secondary_connection.identity,
                principal_id="principal_2",
                vault_id=secondary_vault.vault_id,
                provider="github",
                connection_names=["work"],
                last_used_connection="work",
            ).model_dump_json(),
            collection=f"vault:{secondary_vault.vault_id}",
        )
        await vault.put(
            build_store_key(
                vault=secondary_vault.vault_id,
                provider="github",
                record_type="connection",
                connection=secondary_connection.connection_name,
            ),
            secondary_connection.model_dump_json(),
            collection=f"vault:{secondary_vault.vault_id}",
        )

        await service.revoke("github", vault_ids=[primary_vault.vault_id, secondary_vault.vault_id])

        assert (
            await vault.get(
                build_store_key(provider="github", record_type="server"),
                collection="server",
            )
            is None
        )
        assert (
            await vault.get(
                build_store_key(vault=primary_vault.vault_id, provider="github", record_type="metadata"),
                collection=f"vault:{primary_vault.vault_id}",
            )
            is None
        )
        assert (
            await vault.get(
                build_store_key(
                    vault=primary_vault.vault_id,
                    provider="github",
                    record_type="connection",
                    connection=primary_connection.connection_name,
                ),
                collection=f"vault:{primary_vault.vault_id}",
            )
            is None
        )
        assert (
            await vault.get(
                build_store_key(vault=secondary_vault.vault_id, provider="github", record_type="metadata"),
                collection=f"vault:{secondary_vault.vault_id}",
            )
            is None
        )
        assert (
            await vault.get(
                build_store_key(
                    vault=secondary_vault.vault_id,
                    provider="github",
                    record_type="connection",
                    connection=secondary_connection.connection_name,
                ),
                collection=f"vault:{secondary_vault.vault_id}",
            )
            is None
        )
    finally:
        await store.close()
