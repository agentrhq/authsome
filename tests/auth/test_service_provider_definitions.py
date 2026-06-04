from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from authsome.auth.models.connection import ProviderClientRecord
from authsome.auth.models.enums import AuthType, FlowType
from authsome.auth.models.provider import ApiKeyConfig, ProviderDefinition
from authsome.identity.principal import PrincipalRole
from authsome.server.credential_repository import CredentialRepository
from authsome.server.credential_service import CredentialService
from authsome.server.provider_repository import ProviderRepository
from authsome.server.store import create_server_store
from authsome.vault import Vault


def _provider(name: str = "custom-api") -> ProviderDefinition:
    return ProviderDefinition(
        name=name,
        display_name="Custom API",
        auth_type=AuthType.API_KEY,
        flow=FlowType.API_KEY,
        api_key=ApiKeyConfig(header_name="Authorization"),
    )


@pytest.mark.asyncio
async def test_custom_provider_definition_is_stored_in_store_not_vault(tmp_path: Path) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        vault = AsyncMock(spec=Vault)
        service = CredentialService(
            credentials=CredentialRepository(
                vault,
                identity="steady-wisely-boldly-0042",
                principal_id=None,
                vault_id="vault_test",
            ),
            providers=ProviderRepository(store.provider_definitions),
            identity="steady-wisely-boldly-0042",
            principal_role=PrincipalRole.ADMIN,
            vault_id="vault_test",
        )

        await service.register_provider(_provider())

        assert await store.provider_definitions.get("custom-api") is not None
        vault.put.assert_not_awaited()
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_provider_client_credentials_still_use_vault(tmp_path: Path) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        vault = AsyncMock(spec=Vault)
        service = CredentialService(
            credentials=CredentialRepository(
                vault,
                identity="steady-wisely-boldly-0042",
                principal_id=None,
                vault_id="vault_test",
            ),
            providers=ProviderRepository(store.provider_definitions),
            identity="steady-wisely-boldly-0042",
            vault_id="vault_test",
        )

        await service._credentials.save_provider_client(ProviderClientRecord(provider="github", client_id="cid"))

        vault.put.assert_awaited_once()
        assert vault.put.await_args.kwargs == {"collection": "server"}
    finally:
        await store.close()
