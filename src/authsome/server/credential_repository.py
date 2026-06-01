"""Server-owned repository for credential records stored in Vault."""

from __future__ import annotations

import json
from typing import NamedTuple

from loguru import logger

from authsome.auth.models.connection import (
    ConnectionRecord,
    ProviderClientRecord,
    ProviderMetadataRecord,
    ProviderStateRecord,
)
from authsome.vault import Vault


class StoreKeyParts(NamedTuple):
    """Parsed components of a credential store key."""

    vault: str | None = None
    provider: str | None = None
    record_type: str | None = None
    connection: str | None = None


def build_store_key(
    *,
    vault: str | None = None,
    provider: str | None = None,
    record_type: str | None = None,
    connection: str | None = None,
) -> str:
    """Build a namespaced key for server-owned credential storage."""
    if record_type == "definition" and provider:
        return f"provider:{provider}:definition"
    if record_type == "server" and provider:
        return f"server:provider:{provider}:client"

    if vault and provider:
        if record_type == "metadata":
            return f"vault:{vault}:{provider}:metadata"
        if record_type == "state":
            return f"vault:{vault}:{provider}:state"
        if record_type == "connection" and connection:
            return f"vault:{vault}:{provider}:connection:{connection}"
        if record_type == "client":
            return f"vault:{vault}:{provider}:client"

    raise ValueError(
        f"Cannot build store key with vault={vault}, provider={provider}, "
        f"record_type={record_type}, connection={connection}"
    )


def parse_store_key(key: str) -> StoreKeyParts:
    """Parse a credential store key into its components."""
    if key.startswith("provider:") and key.endswith(":definition"):
        provider = key[len("provider:") : -len(":definition")]
        return StoreKeyParts(provider=provider, record_type="definition")

    if key.startswith("server:provider:") and key.endswith(":client"):
        provider = key[len("server:provider:") : -len(":client")]
        return StoreKeyParts(provider=provider, record_type="server")

    if key.startswith("vault:"):
        parts = key.split(":", 2)
        if len(parts) < 3:
            return StoreKeyParts()
        vault = parts[1]
        remainder = parts[2]

        if remainder.endswith(":metadata"):
            return StoreKeyParts(vault=vault, provider=remainder[:-9], record_type="metadata")
        if remainder.endswith(":state"):
            return StoreKeyParts(vault=vault, provider=remainder[:-6], record_type="state")
        if remainder.endswith(":client"):
            return StoreKeyParts(vault=vault, provider=remainder[:-7], record_type="client")

        if ":connection:" in remainder:
            provider, _, connection = remainder.partition(":connection:")
            return StoreKeyParts(
                vault=vault,
                provider=provider,
                record_type="connection",
                connection=connection,
            )

    return StoreKeyParts()


class CredentialRepository:
    """Persist Authsome credential records in vault-backed namespaces."""

    def __init__(
        self,
        vault: Vault,
        *,
        identity: str | None,
        principal_id: str | None,
        vault_id: str,
    ) -> None:
        self._vault = vault
        self._identity = identity
        self._principal_id = principal_id
        self._vault_id = vault_id

    @property
    def vault(self) -> Vault:
        return self._vault

    @property
    def vault_id(self) -> str:
        return self._vault_id

    @property
    def collection(self) -> str:
        return f"vault:{self._vault_id}"

    @property
    def server_collection(self) -> str:
        return "server"

    async def list_connection_keys(self) -> list[str]:
        prefix = f"vault:{self._vault_id}:"
        keys = await self._vault.list(prefix, collection=self.collection)
        return [key for key in keys if parse_store_key(key).record_type == "connection"]

    async def get_connection(self, provider: str, connection: str) -> ConnectionRecord | None:
        key = build_store_key(
            vault=self._vault_id,
            provider=provider,
            record_type="connection",
            connection=connection,
        )
        raw = await self._vault.get(key, collection=self.collection)
        if raw is None:
            return None
        return self.load_connection_record(raw, key)

    async def save_connection(self, record: ConnectionRecord) -> None:
        record.identity = self._identity
        record.principal_id = self._principal_id
        record.vault_id = self._vault_id
        key = build_store_key(
            vault=self._vault_id,
            provider=record.provider,
            record_type="connection",
            connection=record.connection_name,
        )
        await self._vault.put(key, record.model_dump_json(), collection=self.collection)

    async def delete_connection(self, provider: str, connection: str) -> None:
        key = build_store_key(
            vault=self._vault_id,
            provider=provider,
            record_type="connection",
            connection=connection,
        )
        await self._vault.delete(key, collection=self.collection)

    async def get_provider_metadata(self, provider: str) -> ProviderMetadataRecord | None:
        key = build_store_key(vault=self._vault_id, provider=provider, record_type="metadata")
        raw = await self._vault.get(key, collection=self.collection)
        return ProviderMetadataRecord.model_validate_json(raw) if raw else None

    async def save_provider_metadata(self, record: ProviderMetadataRecord) -> None:
        record.identity = self._identity
        record.principal_id = self._principal_id
        record.vault_id = self._vault_id
        key = build_store_key(vault=self._vault_id, provider=record.provider, record_type="metadata")
        await self._vault.put(key, record.model_dump_json(), collection=self.collection)

    async def delete_provider_metadata(self, provider: str) -> None:
        key = build_store_key(vault=self._vault_id, provider=provider, record_type="metadata")
        await self._vault.delete(key, collection=self.collection)

    async def get_provider_state(self, provider: str) -> ProviderStateRecord | None:
        key = build_store_key(vault=self._vault_id, provider=provider, record_type="state")
        raw = await self._vault.get(key, collection=self.collection)
        return ProviderStateRecord.model_validate_json(raw) if raw else None

    async def save_provider_state(self, record: ProviderStateRecord) -> None:
        record.identity = self._identity
        record.principal_id = self._principal_id
        record.vault_id = self._vault_id
        key = build_store_key(vault=self._vault_id, provider=record.provider, record_type="state")
        await self._vault.put(key, record.model_dump_json(), collection=self.collection)

    async def get_provider_client(self, provider: str) -> ProviderClientRecord | None:
        key = build_store_key(provider=provider, record_type="server")
        raw = await self._vault.get(key, collection=self.server_collection)
        return ProviderClientRecord.model_validate_json(raw) if raw else None

    async def save_provider_client(self, record: ProviderClientRecord) -> None:
        key = build_store_key(provider=record.provider, record_type="server")
        await self._vault.put(key, record.model_dump_json(), collection=self.server_collection)

    async def delete_provider_client(self, provider: str) -> None:
        key = build_store_key(provider=provider, record_type="server")
        await self._vault.delete(key, collection=self.server_collection)

    @staticmethod
    def load_connection_record(raw: str, key: str) -> ConnectionRecord | None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Corrupt record at key {}", key)
            return None
        if data.get("schema_version", 1) < 2:
            return None
        return ConnectionRecord.model_validate(data)
