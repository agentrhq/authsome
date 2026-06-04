"""Server-owned provider definition repository."""

import builtins
import importlib.resources
import json

from loguru import logger

from authsome.auth.models.provider import ProviderDefinition
from authsome.errors import ProviderNotFoundError
from authsome.server.store.repositories import ProviderDefinitionRepository


class ProviderRepository:
    """Resolve bundled and custom provider definitions."""

    def __init__(self, custom: ProviderDefinitionRepository) -> None:
        self._custom = custom
        self._bundled: dict[str, ProviderDefinition] | None = None

    def _load_bundled(self) -> dict[str, ProviderDefinition]:
        if self._bundled is not None:
            return self._bundled

        bundled: dict[str, ProviderDefinition] = {}
        try:
            files = importlib.resources.files("authsome.auth.bundled_providers")
            for file in files.iterdir():
                if file.name.endswith(".json"):
                    with file.open("r", encoding="utf-8") as handle:
                        definition = ProviderDefinition.model_validate(json.load(handle))
                    bundled[definition.name] = definition
        except Exception as exc:
            logger.warning("Error loading bundled providers: {}", exc)

        self._bundled = bundled
        return bundled

    async def get(self, name: str) -> ProviderDefinition:
        custom = await self._custom.get(name)
        if custom is not None:
            return custom
        bundled = self._load_bundled()
        if name in bundled:
            return bundled[name]
        raise ProviderNotFoundError(name)

    async def list(self) -> builtins.list[ProviderDefinition]:
        providers = {**self._load_bundled()}
        providers.update({provider.name: provider for provider in await self._custom.list()})
        return sorted(providers.values(), key=lambda provider: provider.name)

    async def list_by_source(self) -> dict[str, builtins.list[ProviderDefinition]]:
        bundled = sorted(self._load_bundled().values(), key=lambda provider: provider.name)
        custom = sorted(await self._custom.list(), key=lambda provider: provider.name)
        return {"bundled": bundled, "custom": custom}

    async def save_custom(self, definition: ProviderDefinition, *, force: bool = False) -> None:
        await self._custom.save(definition, force=force)

    async def delete_custom(self, name: str) -> bool:
        return await self._custom.delete(name)

    async def is_custom(self, name: str) -> bool:
        return await self._custom.get(name) is not None
