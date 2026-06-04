from pathlib import Path

import pytest

from authsome.auth.models.connection import (
    ConnectionRecord,
    ProviderClientRecord,
    ProviderMetadataRecord,
    ProviderStateRecord,
)
from authsome.auth.models.enums import AuthType, ConnectionStatus
from authsome.server.credential_repository import CredentialRepository, StoreKeyParts, build_store_key, parse_store_key
from authsome.server.dependencies import create_vault


def _connection() -> ConnectionRecord:
    return ConnectionRecord(
        provider="github",
        connection_name="default",
        auth_type=AuthType.OAUTH2,
        status=ConnectionStatus.CONNECTED,
        access_token="access-token",
    )


@pytest.mark.asyncio
async def test_connection_roundtrip_preserves_vault_key_format(tmp_path: Path) -> None:
    vault = await create_vault(tmp_path)
    repo = CredentialRepository(
        vault,
        identity="steady-wisely-boldly-0042",
        principal_id="principal_1",
        vault_id="vault_1",
    )

    await repo.save_connection(_connection())

    key = build_store_key(vault="vault_1", provider="github", record_type="connection", connection="default")
    raw = await vault.get(key, collection="vault:vault_1")
    loaded = await repo.get_connection("github", "default")

    assert raw is not None
    assert loaded is not None
    assert loaded.identity == "steady-wisely-boldly-0042"
    assert loaded.principal_id == "principal_1"
    assert loaded.vault_id == "vault_1"
    assert loaded.access_token == "access-token"


@pytest.mark.asyncio
async def test_connection_delete(tmp_path: Path) -> None:
    vault = await create_vault(tmp_path)
    repo = CredentialRepository(vault, identity="agent", principal_id="principal_1", vault_id="vault_1")

    await repo.save_connection(_connection())
    await repo.delete_connection("github", "default")

    assert await repo.get_connection("github", "default") is None


@pytest.mark.asyncio
async def test_metadata_state_and_client_roundtrip(tmp_path: Path) -> None:
    vault = await create_vault(tmp_path)
    repo = CredentialRepository(vault, identity="agent", principal_id="principal_1", vault_id="vault_1")

    metadata = ProviderMetadataRecord(provider="github", connection_names=["default"])
    state = ProviderStateRecord(provider="github")
    client = ProviderClientRecord(provider="github", client_id="cid", client_secret="secret")

    await repo.save_provider_metadata(metadata)
    await repo.save_provider_state(state)
    await repo.save_provider_client(client)

    loaded_metadata = await repo.get_provider_metadata("github")
    loaded_state = await repo.get_provider_state("github")
    loaded_client = await repo.get_provider_client("github")

    assert loaded_metadata is not None
    assert loaded_metadata.vault_id == "vault_1"
    assert loaded_metadata.connection_names == ["default"]
    assert loaded_state is not None
    assert loaded_state.vault_id == "vault_1"
    assert loaded_client is not None
    assert loaded_client.client_id == "cid"

    server_key = build_store_key(provider="github", record_type="server")
    assert await vault.get(server_key, collection="server") is not None


@pytest.mark.asyncio
async def test_list_connection_keys_returns_existing_connection_keys(tmp_path: Path) -> None:
    vault = await create_vault(tmp_path)
    repo = CredentialRepository(vault, identity="agent", principal_id="principal_1", vault_id="vault_1")

    await repo.save_connection(_connection())

    keys = await repo.list_connection_keys()

    assert keys == [build_store_key(vault="vault_1", provider="github", record_type="connection", connection="default")]


def test_build_store_key() -> None:
    assert build_store_key(record_type="definition", provider="github") == "provider:github:definition"
    assert build_store_key(vault="vault_default", provider="github", record_type="metadata") == (
        "vault:vault_default:github:metadata"
    )
    assert build_store_key(vault="vault_default", provider="github", record_type="state") == (
        "vault:vault_default:github:state"
    )
    assert (
        build_store_key(
            vault="vault_default",
            provider="github",
            record_type="connection",
            connection="personal",
        )
        == "vault:vault_default:github:connection:personal"
    )
    assert build_store_key(vault="vault_default", provider="github", record_type="client") == (
        "vault:vault_default:github:client"
    )
    assert build_store_key(provider="github", record_type="server") == "server:provider:github:client"

    with pytest.raises(ValueError):
        build_store_key(vault="vault_default", provider="github", record_type="unknown")

    with pytest.raises(ValueError):
        build_store_key(record_type="metadata")


def test_parse_store_key_server() -> None:
    assert parse_store_key("server:provider:github:client") == StoreKeyParts(
        vault=None,
        provider="github",
        record_type="server",
        connection=None,
    )
