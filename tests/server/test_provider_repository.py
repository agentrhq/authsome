from __future__ import annotations

from pathlib import Path

import pytest

from authsome.auth.models.enums import AuthType, FlowType
from authsome.auth.models.provider import ApiKeyConfig, ProviderDefinition
from authsome.server.provider_repository import ProviderRepository
from authsome.server.store import create_server_store


def _custom_provider(name: str = "github") -> ProviderDefinition:
    return ProviderDefinition(
        name=name,
        display_name="Custom GitHub",
        auth_type=AuthType.API_KEY,
        flow=FlowType.API_KEY,
        api_key=ApiKeyConfig(header_name="Authorization"),
    )


@pytest.mark.asyncio
async def test_bundled_provider_loads(tmp_path: Path) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        providers = ProviderRepository(store.provider_definitions)

        github = await providers.get("github")

        assert github.name == "github"
        assert await providers.is_custom("github") is False
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_custom_provider_overrides_bundled(tmp_path: Path) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        providers = ProviderRepository(store.provider_definitions)
        await providers.save_custom(_custom_provider("github"), force=True)

        github = await providers.get("github")

        assert github.display_name == "Custom GitHub"
        assert await providers.is_custom("github") is True
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_delete_custom_exposes_bundled_fallback(tmp_path: Path) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        providers = ProviderRepository(store.provider_definitions)
        await providers.save_custom(_custom_provider("github"), force=True)

        removed = await providers.delete_custom("github")
        github = await providers.get("github")

        assert removed is True
        assert github.name == "github"
        assert github.display_name != "Custom GitHub"
        assert await providers.is_custom("github") is False
    finally:
        await store.close()


@pytest.mark.asyncio
async def test_list_by_source_separates_bundled_and_custom(tmp_path: Path) -> None:
    store = await create_server_store(home=tmp_path)
    try:
        providers = ProviderRepository(store.provider_definitions)
        await providers.save_custom(_custom_provider("custom-only"), force=True)

        by_source = await providers.list_by_source()

        assert any(provider.name == "github" for provider in by_source["bundled"])
        assert [provider.name for provider in by_source["custom"]] == ["custom-only"]
    finally:
        await store.close()
