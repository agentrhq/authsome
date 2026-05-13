"""AuthService — authentication and credential lifecycle service.

Owns OAuth flows, token refresh, login/logout/revoke.
Receives only a Vault.  All persistence goes through the Vault.
"""

from __future__ import annotations

import importlib.resources
import json
from datetime import timedelta
from typing import Any
from urllib.parse import urlparse

from loguru import logger

from authsome import audit
from authsome.auth.flows.api_key import ApiKeyFlow
from authsome.auth.flows.base import AuthFlow
from authsome.auth.flows.dcr_pkce import DcrPkceFlow
from authsome.auth.flows.device_code import DeviceCodeFlow
from authsome.auth.flows.pkce import PkceFlow
from authsome.auth.input_provider import InputField
from authsome.auth.models.connection import (
    ConnectionRecord,
    ProviderClientRecord,
    ProviderMetadataRecord,
    ProviderStateRecord,
)
from authsome.auth.models.enums import AuthType, ConnectionStatus, ExportFormat, FlowType
from authsome.auth.models.provider import ProviderDefinition
from authsome.auth.sessions import AuthSession
from authsome.auth.utils import export_name_part, normalize_base_url, normalize_scopes
from authsome.errors import (
    AuthsomeError,
    ConnectionNotFoundError,
    CredentialMissingError,
    IdentityNotFoundError,
    InvalidProviderSchemaError,
    ProviderAlreadyRegisteredError,
    ProviderNotFoundError,
    RefreshFailedError,
    TokenExpiredError,
    UnsupportedFlowError,
)
from authsome.utils import build_store_key, format_duration, is_filesystem_safe, parse_store_key, utc_now
from authsome.vault import Vault

_VALID_FLOWS: dict[AuthType, set[FlowType]] = {
    AuthType.OAUTH2: {FlowType.PKCE, FlowType.DEVICE_CODE, FlowType.DCR_PKCE},
    AuthType.API_KEY: {FlowType.API_KEY},
}

_NEAR_EXPIRY_SECONDS = 300

_FLOW_HANDLERS: dict[FlowType, type[AuthFlow]] = {
    FlowType.PKCE: PkceFlow,
    FlowType.DEVICE_CODE: DeviceCodeFlow,
    FlowType.DCR_PKCE: DcrPkceFlow,
    FlowType.API_KEY: ApiKeyFlow,
}


class AuthService:
    """
    Authentication and credential lifecycle service.

    All reads and writes go through self._vault.
    Key construction (identity:<identity>:<provider>:...) lives here.
    """

    def __init__(
        self,
        vault: Vault,
        identity: str,
    ) -> None:
        if not identity:
            raise ValueError("AuthService requires an explicit identity handle")
        self._vault = vault
        self._identity = identity
        self._bundled: dict[str, ProviderDefinition] = self._load_bundled_providers()

    @property
    def _coll(self) -> str:
        """Vault collection for the active identity's credentials."""
        return f"vault:{self._identity}"

    @property
    def vault(self) -> Vault:
        return self._vault

    @property
    def identity(self) -> str:
        return self._identity

    # ── Provider operations ───────────────────────────────────────────────

    @staticmethod
    def _load_bundled_providers() -> dict[str, ProviderDefinition]:
        bundled: dict[str, ProviderDefinition] = {}
        try:
            files = importlib.resources.files("authsome.auth.bundled_providers")
            for file in files.iterdir():
                if file.name.endswith(".json"):
                    with file.open("r", encoding="utf-8") as f:
                        data = json.load(f)
                        defn = ProviderDefinition.model_validate(data)
                        bundled[defn.name] = defn
        except Exception as e:
            logger.warning("Error loading bundled providers: {}", e)
        return bundled

    async def _load_custom_providers(self) -> dict[str, ProviderDefinition]:
        providers: dict[str, ProviderDefinition] = {}
        try:
            for name in await self._vault.list(collection="providers"):
                raw = await self._vault.get(name, collection="providers")
                if raw:
                    providers[name] = ProviderDefinition.model_validate_json(raw)
        except Exception as exc:
            logger.warning("Could not load custom providers: {}", exc)
        return providers

    async def list_providers(self) -> list[ProviderDefinition]:
        providers = {**self._bundled, **(await self._load_custom_providers())}
        return sorted(providers.values(), key=lambda p: p.name)

    async def list_providers_by_source(self) -> dict[str, list[ProviderDefinition]]:
        bundled_list = sorted(self._bundled.values(), key=lambda p: p.name)
        custom_providers = await self._load_custom_providers()
        custom_list = sorted(custom_providers.values(), key=lambda p: p.name)
        return {"bundled": bundled_list, "custom": custom_list}

    async def get_provider(self, provider: str) -> ProviderDefinition:
        raw = await self._vault.get(provider, collection="providers")
        if raw:
            return ProviderDefinition.model_validate_json(raw)
        if provider in self._bundled:
            return self._bundled[provider]
        raise ProviderNotFoundError(provider)

    async def is_local_provider(self, provider: str) -> bool:
        """Check if a provider is a custom/local provider."""
        val = await self._vault.get(provider, collection="providers")
        return val is not None

    async def proxy_routes(self) -> dict[str, Any]:
        """Build the list of routes for proxy routing."""
        from urllib.parse import urlparse

        routes = []
        for provider_group in await self.list_connections():
            provider_name = provider_group["name"]
            selected_connections = provider_group["connections"]

            try:
                definition = await self.get_provider(provider_name)
            except Exception:
                continue
            if not definition.host_url:
                continue

            # Find the default connection
            default_conn = next((c for c in selected_connections if c.get("is_default")), None)
            if not default_conn:
                continue

            paths: set[str] = set()
            if definition.oauth:
                for raw_url in [
                    definition.oauth.authorization_url,
                    definition.oauth.token_url,
                    definition.oauth.revocation_url,
                    definition.oauth.device_authorization_url,
                    (definition.registration.registration_endpoint if definition.registration else None),
                ]:
                    if not raw_url:
                        continue
                    parsed = urlparse(raw_url)
                    paths.add(parsed.path or "/")

            routes.append(
                {
                    "provider": provider_name,
                    "connection": default_conn.get("connection_name", "default"),
                    "host_url": definition.host_url,
                    "auth_endpoint_paths": sorted(list(paths)),
                }
            )
        routes.sort(key=lambda r: (r["host_url"].startswith("regex:"), r["provider"]))
        return {"routes": routes}

    async def resolve_credentials(self, **kwargs: Any) -> dict[str, Any]:
        """Resolve credentials for a provider/connection pair."""
        provider = kwargs["provider"]
        connection = kwargs.get("connection")
        resolved_connection = await self.resolve_connection_name(provider, connection)
        record = await self.get_connection(provider, resolved_connection)
        headers = await self.get_auth_headers(provider, resolved_connection)
        return {
            "provider": provider,
            "connection": resolved_connection,
            "headers": headers,
            "expires_at": record.expires_at.isoformat() if record.expires_at else None,
        }

    async def register_provider(self, definition: ProviderDefinition, *, force: bool = False) -> None:
        self._validate_provider(definition)
        has_custom = (await self._vault.get(definition.name, collection="providers")) is not None
        if force or not has_custom:
            await self._vault.put(
                definition.name,
                definition.model_dump_json(indent=2, exclude_none=True),
                collection="providers",
            )
        else:
            raise ProviderAlreadyRegisteredError(definition.name)
        logger.info("Registered provider: {}", definition.name)

    async def remove_provider(self, name: str) -> bool:
        """Remove a custom provider. Returns True if removed."""
        return await self._vault.delete(name, collection="providers")

    def _validate_provider(self, definition: ProviderDefinition) -> None:
        if not is_filesystem_safe(definition.name):
            raise InvalidProviderSchemaError(
                f"Provider name '{definition.name}' is not filesystem-safe", provider=definition.name
            )
        valid_flows = _VALID_FLOWS.get(definition.auth_type)
        if valid_flows is None:
            raise InvalidProviderSchemaError(
                f"Unrecognized auth_type: {definition.auth_type}", provider=definition.name
            )
        if definition.flow not in valid_flows:
            raise InvalidProviderSchemaError(
                f"Flow '{definition.flow}' is not valid for auth_type '{definition.auth_type}'. "
                f"Valid flows: {[f.value for f in valid_flows]}",
                provider=definition.name,
            )
        if definition.auth_type == AuthType.OAUTH2 and definition.oauth is None:
            raise InvalidProviderSchemaError(
                "auth_type 'oauth2' requires an 'oauth' configuration section", provider=definition.name
            )
        if definition.auth_type == AuthType.API_KEY and definition.api_key is None:
            raise InvalidProviderSchemaError(
                "auth_type 'api_key' requires an 'api_key' configuration section", provider=definition.name
            )
        if definition.oauth:
            for field_name in ("authorization_url", "token_url"):
                url = getattr(definition.oauth, field_name, None)
                if url:
                    self._validate_url(url, field_name, definition.name)

    @staticmethod
    def _validate_url(url: str, field_name: str, provider_name: str) -> None:
        if "{base_url}" in url:
            return
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise InvalidProviderSchemaError(f"Invalid URL for '{field_name}': {url}", provider=provider_name)

    # ── Connection operations ─────────────────────────────────────────────

    async def list_connections(self) -> list[dict[str, Any]]:
        prefix = f"identity:{self._identity}:"
        keys = await self._vault.list(prefix, collection=self._coll)

        providers: dict[str, list[dict[str, Any]]] = {}
        defaults: dict[str, str] = {}
        for key in keys:
            parts = parse_store_key(key)
            if parts.record_type == "connection" and parts.provider and parts.connection:
                provider_name = parts.provider
                connection_name = parts.connection
                if provider_name not in defaults:
                    meta_key = build_store_key(identity=self._identity, provider=provider_name, record_type="metadata")
                    meta_json = await self._vault.get(meta_key, collection=self._coll)
                    if meta_json:
                        defaults[provider_name] = ProviderMetadataRecord.model_validate_json(
                            meta_json
                        ).default_connection
                    else:
                        defaults[provider_name] = "default"
                record_json = await self._vault.get(key, collection=self._coll)
                if record_json:
                    record = self._load_connection_record(record_json, key)
                    if record is None:
                        continue
                    if provider_name not in providers:
                        providers[provider_name] = []
                    providers[provider_name].append(
                        {
                            "connection_name": connection_name,
                            "is_default": connection_name == defaults.get(provider_name, "default"),
                            "auth_type": record.auth_type.value,
                            "status": record.status.value,
                            "scopes": record.scopes,
                            "base_url": record.base_url,
                            "host_url": record.host_url,
                            "expires_at": record.expires_at.isoformat() if record.expires_at else None,
                        }
                    )

        return [
            {"name": pname, "default_connection": defaults.get(pname, "default"), "connections": conns}
            for pname, conns in sorted(providers.items())
        ]

    async def get_connection(
        self,
        provider: str,
        connection: str = "default",
    ) -> ConnectionRecord:
        connection = await self.resolve_connection_name(provider, connection)
        key = build_store_key(
            identity=self._identity, provider=provider, record_type="connection", connection=connection
        )
        record_json = await self._vault.get(key, collection=self._coll)
        if not record_json:
            raise ConnectionNotFoundError(provider=provider, connection=connection, identity=self._identity)
        record = self._load_connection_record(record_json, key)
        if record is None:
            raise AuthsomeError(
                f"Stored credentials for '{provider}' use the old v1 format. "
                "Please run: authsome revoke {provider} && authsome login {provider}"
            )
        return record

    async def resolve_connection_name(self, provider: str, connection: str | None = None) -> str:
        """Resolve an optional connection name to the provider default."""
        if connection:
            return connection
        meta_key = build_store_key(identity=self._identity, provider=provider, record_type="metadata")
        existing_json = await self._vault.get(meta_key, collection=self._coll)
        if existing_json:
            metadata = ProviderMetadataRecord.model_validate_json(existing_json)
            return metadata.default_connection
        return "default"

    async def get_provider_client(self, provider: str) -> ProviderClientRecord | None:
        """Return stored client credentials for a provider, or None if absent.

        Public read-only accessor. The secret field is still stored encrypted at rest;
        callers are responsible for redacting before display.
        """
        return await self._get_provider_client_credentials(provider)

    async def set_default_connection(self, provider: str, connection: str) -> None:
        """Set the default connection for a provider."""
        await self.get_connection(provider, connection)
        meta_key = build_store_key(identity=self._identity, provider=provider, record_type="metadata")
        existing_json = await self._vault.get(meta_key, collection=self._coll)
        if existing_json:
            metadata = ProviderMetadataRecord.model_validate_json(existing_json)
        else:
            metadata = ProviderMetadataRecord(identity=self._identity, provider=provider)
        if connection not in metadata.connection_names:
            metadata.connection_names.append(connection)
        metadata.default_connection = connection
        metadata.last_used_connection = connection
        await self._vault.put(meta_key, metadata.model_dump_json(), collection=self._coll)

    # ── Authentication ────────────────────────────────────────────────────

    async def get_required_inputs(
        self,
        session: AuthSession,
        scopes: list[str] | None = None,
        base_url: str | None = None,
    ) -> list[InputField]:
        """Determine what inputs are missing for a given session."""
        from authsome.auth.input_provider import InputField

        provider = session.provider
        definition = await self.get_provider(provider)
        flow_type = FlowType(session.flow_type)
        client_record = await self._get_provider_client_credentials(provider)

        flow_base_url = base_url or (client_record.base_url if client_record else None)
        flow_client_id = client_record.client_id if client_record else None
        persisted_scopes = client_record.scopes if client_record else None

        fields: list[InputField] = []

        if definition.oauth and definition.oauth.base_url and not flow_base_url:
            fields.append(
                InputField(
                    name="base_url",
                    label="Base URL",
                    secret=False,
                    default=definition.oauth.base_url,
                )
            )
            fields.append(
                InputField(
                    name="host_url",
                    label="API Host URL",
                    secret=False,
                    default=definition.host_url or "",
                )
            )

        if flow_type == FlowType.PKCE and not flow_client_id:
            fields.append(InputField(name="client_id", label="Client ID", secret=False))
            fields.append(InputField(name="client_secret", label="Client Secret (Optional)", secret=True, default=""))
        elif flow_type == FlowType.DEVICE_CODE and not flow_client_id:
            fields.append(
                InputField(
                    name="client_id",
                    label="Client ID (leave blank for public device code flow)",
                    secret=False,
                    default="",
                )
            )
            fields.append(InputField(name="client_secret", label="Client Secret (Optional)", secret=True, default=""))

        if flow_type in (FlowType.PKCE, FlowType.DEVICE_CODE, FlowType.DCR_PKCE):
            if scopes is None and persisted_scopes is None:
                default_scopes = (
                    ",".join(definition.oauth.scopes) if definition.oauth and definition.oauth.scopes else ""
                )
                fields.append(
                    InputField(name="scopes", label="Scopes (comma-separated)", secret=False, default=default_scopes)
                )

        if flow_type == FlowType.API_KEY:
            api_key_field = InputField(name="api_key", label="API Key", secret=True)
            if definition.api_key and definition.api_key.key_pattern:
                api_key_field.pattern = definition.api_key.key_pattern
                api_key_field.pattern_hint = definition.api_key.key_pattern_hint
            fields.append(api_key_field)

        return fields

    async def save_inputs(self, session: AuthSession, inputs: dict[str, str]) -> None:
        """Save collected inputs to the Vault or session payload."""
        from authsome.auth.models.connection import ProviderClientRecord

        provider = session.provider
        flow_type = FlowType(session.flow_type)
        client_record = await self._get_provider_client_credentials(provider)

        if flow_type in (FlowType.PKCE, FlowType.DEVICE_CODE, FlowType.DCR_PKCE):
            if client_record is None:
                client_record = ProviderClientRecord(identity=self._identity, provider=provider)
            if inputs.get("base_url"):
                client_record.base_url = inputs["base_url"]
                session.payload["base_url"] = inputs["base_url"]
            if inputs.get("host_url"):
                client_record.host_url = inputs["host_url"]
            if inputs.get("client_id"):
                client_record.client_id = inputs["client_id"]
            if inputs.get("client_secret"):
                client_record.client_secret = inputs["client_secret"]
            if "scopes" in inputs:
                scopes_input = inputs["scopes"].strip()
                client_record.scopes = [s.strip() for s in scopes_input.split(",") if s.strip()] if scopes_input else []
            await self._save_provider_client_credentials(client_record)
        elif flow_type == FlowType.API_KEY:
            api_key = inputs.get("api_key")
            if api_key:
                session.payload["api_key"] = api_key

    async def begin_login_flow(
        self,
        session: AuthSession,
        scopes: list[str] | None = None,
        flow_override: FlowType | None = None,
        force: bool = False,
        base_url: str | None = None,
    ) -> None:
        provider = session.provider
        connection_name = session.connection_name
        definition = await self.get_provider(provider)

        flow_type = flow_override or FlowType(session.flow_type)
        handler_cls = _FLOW_HANDLERS.get(flow_type)
        if handler_cls is None:
            raise UnsupportedFlowError(flow_type.value, provider=provider)

        handler = handler_cls()
        client_record = await self._get_provider_client_credentials(provider)

        flow_client_id = client_record.client_id if client_record else None
        flow_client_secret = client_record.client_secret if client_record else None
        flow_base_url = base_url or (client_record.base_url if client_record else None)

        final_scopes = (
            scopes
            if scopes is not None
            else (client_record.scopes if client_record and client_record.scopes is not None else None)
        )

        resolved_definition = definition.resolve_urls(flow_base_url)

        await handler.begin(
            provider=resolved_definition,
            identity=self._identity,
            connection_name=connection_name,
            runtime_session=session,
            scopes=final_scopes,
            client_id=flow_client_id,
            client_secret=flow_client_secret,
            base_url=flow_base_url,
        )

    async def resume_login_flow(
        self,
        session: AuthSession,
        callback_data: dict[str, Any],
    ) -> ConnectionRecord | None:
        provider = session.provider
        connection_name = session.connection_name
        definition = await self.get_provider(provider)

        from authsome.auth.models.enums import FlowType

        flow_type = FlowType(session.flow_type)
        handler_cls = _FLOW_HANDLERS.get(flow_type)
        if handler_cls is None:
            raise UnsupportedFlowError(flow_type.value, provider=provider)

        handler = handler_cls()
        client_record = await self._get_provider_client_credentials(provider)

        flow_client_id = client_record.client_id if client_record else None
        flow_client_secret = client_record.client_secret if client_record else None

        flow_base_url = session.payload.get("base_url") or (client_record.base_url if client_record else None)
        resolved_definition = definition.resolve_urls(flow_base_url)

        result = await handler.resume(
            provider=resolved_definition,
            identity=self._identity,
            connection_name=connection_name,
            runtime_session=session,
            callback_data=callback_data,
            client_id=flow_client_id,
            client_secret=flow_client_secret,
        )

        if result is None or result.connection is None:
            return None

        if result.client_record is not None:
            if client_record is None:
                client_record = ProviderClientRecord(identity=self._identity, provider=provider)
            client_record.client_id = result.client_record.client_id
            client_record.client_secret = result.client_record.client_secret
            client_record.base_url = result.client_record.base_url or client_record.base_url
            await self._save_provider_client_credentials(client_record)

        result.connection.base_url = flow_base_url
        result.connection.host_url = resolved_definition.host_url

        await self._save_connection(result.connection)
        await self._update_provider_metadata(provider, connection_name)

        logger.info(
            "Login successful: provider={} connection={} identity={}",
            provider,
            connection_name,
            self._identity,
        )
        return result.connection

    async def background_resume(self, session: AuthSession) -> None:
        """Resume a flow in a background thread."""
        from authsome.auth.sessions import AuthSessionStatus

        try:
            await self.resume_login_flow(session, {})
            session.state = AuthSessionStatus.COMPLETED
            session.status_message = "Login successful"
        except Exception as e:
            session.state = AuthSessionStatus.FAILED
            session.error_message = str(e)

    @staticmethod
    def _connection_is_valid(record: ConnectionRecord) -> bool:
        if record.status != ConnectionStatus.CONNECTED:
            return False
        if record.expires_at is None:
            return True
        return utc_now() < record.expires_at

    @classmethod
    def _requested_context_matches(
        cls,
        record: ConnectionRecord,
        *,
        scopes: list[str] | None,
        base_url: str | None,
    ) -> bool:
        if scopes is not None and normalize_scopes(scopes) != normalize_scopes(record.scopes):
            return False
        if base_url is not None and normalize_base_url(base_url) != normalize_base_url(record.base_url):
            return False
        return True

    @staticmethod
    def _build_docs_hints(definition: ProviderDefinition, flow_type: FlowType) -> list[dict[str, Any]]:
        """Convert provider docs URL into a bridge instruction block."""
        if not definition.docs:
            return []

        if flow_type not in (FlowType.PKCE, FlowType.DEVICE_CODE, FlowType.DCR_PKCE, FlowType.API_KEY):
            return []

        return [
            {
                "type": "instructions",
                "label": "Instructions",
                "url": definition.docs,
            }
        ]

    # ── Token operations ──────────────────────────────────────────────────

    async def get_access_token(self, provider: str, connection: str = "default") -> str:
        record = await self.get_connection(provider, connection)
        return await self._get_access_token_from_record(record)

    async def get_auth_headers(self, provider: str, connection: str = "default") -> dict[str, str]:
        definition = await self.get_provider(provider)
        record = await self.get_connection(provider, connection)
        return await self._get_auth_headers_from_record(record, definition)

    # ── Lifecycle operations ──────────────────────────────────────────────

    async def logout(self, provider: str, connection: str = "default") -> None:
        definition = await self.get_provider(provider)
        try:
            record = await self.get_connection(provider, connection)
        except ConnectionNotFoundError:
            return

        if record.auth_type == AuthType.OAUTH2 and (record.access_token or record.refresh_token):
            handler_cls = _FLOW_HANDLERS.get(definition.flow)
            if handler_cls:
                handler = handler_cls()
                client_record = await self._get_provider_client_credentials(provider)
                client_id = client_record.client_id if client_record else None
                client_secret = client_record.client_secret if client_record else None

                resolved_definition = definition.resolve_urls(record.base_url)
                await handler.revoke(
                    provider=resolved_definition,
                    record=record,
                    client_id=client_id,
                    client_secret=client_secret,
                )

        key = build_store_key(
            identity=self._identity, provider=provider, record_type="connection", connection=connection
        )
        await self._vault.delete(key, collection=self._coll)
        await self._remove_from_provider_metadata(provider, connection)

    async def revoke(self, provider: str) -> None:
        await self.get_provider(provider)
        meta_key = build_store_key(identity=self._identity, provider=provider, record_type="metadata")
        existing_json = await self._vault.get(meta_key, collection=self._coll)
        if existing_json:
            metadata = ProviderMetadataRecord.model_validate_json(existing_json)
            for conn_name in list(metadata.connection_names):
                await self.logout(provider, connection=conn_name)
        await self._vault.delete(meta_key, collection=self._coll)
        client_key = build_store_key(identity=self._identity, provider=provider, record_type="client")
        await self._vault.delete(client_key, collection=self._coll)

    async def remove(self, provider: str) -> None:
        """Revoke all tokens and remove the provider definition if it is local."""
        await self.revoke(provider)
        if await self.is_local_provider(provider):
            await self._vault.delete(provider, collection="providers")
            logger.info("Removed local provider definition: {}", provider)
        else:
            logger.info("Revoked bundled provider: {} (definition kept)", provider)

    # ── Export operations ─────────────────────────────────────────────────

    async def export(
        self,
        provider: str | None = None,
        connection: str = "default",
        format: ExportFormat = ExportFormat.ENV,
    ) -> str:
        """Export credential material in selected format."""
        values = await self.get_export_values(provider, connection)
        return self._format_export_values(values, format)

    async def get_export_values(self, provider: str | None = None, connection: str = "default") -> dict[str, str]:
        """Return a dictionary of exportable credential values."""
        if provider is None:
            values: dict[str, str] = {}
            for provider_record in await self.list_connections():
                provider_name = provider_record["name"]
                for connection_record in provider_record["connections"]:
                    connection_name = connection_record["connection_name"]
                    exported = await self._export_connection_values(provider_name, connection_name)
                    for env_name, env_value in exported.items():
                        if env_name in values:
                            env_name = self._disambiguate_export_name(env_name, provider_name, connection_name, values)
                        values[env_name] = env_value
            return values

        return await self._export_connection_values(provider, connection)

    async def _export_connection_values(self, provider: str, connection: str) -> dict[str, str]:
        definition = await self.get_provider(provider)
        record = await self.get_connection(provider, connection)
        values: dict[str, str] = {}
        export_map = definition.export.env if definition.export else {}

        if record.auth_type == AuthType.OAUTH2:
            if record.access_token:
                env_name = export_map.get("access_token", f"{export_name_part(provider)}_ACCESS_TOKEN")
                values[env_name] = record.access_token
            if record.refresh_token:
                env_name = export_map.get("refresh_token", f"{export_name_part(provider)}_REFRESH_TOKEN")
                values[env_name] = record.refresh_token
        elif record.auth_type == AuthType.API_KEY:
            if record.api_key:
                env_name = export_map.get("api_key", f"{export_name_part(provider)}_API_KEY")
                values[env_name] = record.api_key

        return values

    def _format_export_values(self, values: dict[str, str], format: ExportFormat) -> str:
        if format == ExportFormat.ENV:
            return "\n".join(f"{k}={v}" for k, v in values.items())
        if format == ExportFormat.SHELL:
            return "\n".join(f"export {k}={v}" for k, v in values.items())
        if format == ExportFormat.JSON:
            return json.dumps(values, indent=2)
        return ""

    def _disambiguate_export_name(
        self, env_name: str, provider: str, connection: str, existing_values: dict[str, str]
    ) -> str:
        suffix = "_".join(
            part
            for part in (
                export_name_part(provider),
                export_name_part(connection),
            )
            if part
        )
        candidate = f"{env_name}_{suffix}" if suffix else env_name
        counter = 2
        while candidate in existing_values:
            candidate = f"{env_name}_{suffix}_{counter}" if suffix else f"{env_name}_{counter}"
            counter += 1
        return candidate

    # ── Identity operations ───────────────────────────────────────────────

    async def get_identity(self, name: str) -> str:
        if name != self._identity:
            raise IdentityNotFoundError(name)
        return self._identity

    # ── Internal helpers ──────────────────────────────────────────────────

    def _load_connection_record(self, record_json: str, key: str) -> ConnectionRecord | None:
        """Load and validate a connection record, detecting v1 format."""
        try:
            data = json.loads(record_json)
        except json.JSONDecodeError:
            logger.warning("Corrupt record at key {}", key)
            return None

        if data.get("schema_version", 1) < 2:
            return None  # v1 data — caller handles detection

        return ConnectionRecord.model_validate(data)

    async def _save_connection(self, record: ConnectionRecord) -> None:
        key = build_store_key(
            identity=self._identity,
            provider=record.provider,
            record_type="connection",
            connection=record.connection_name,
        )
        await self._vault.put(key, record.model_dump_json(), collection=self._coll)

    async def _get_provider_client_credentials(self, provider: str) -> ProviderClientRecord | None:
        key = build_store_key(identity=self._identity, provider=provider, record_type="client")
        record_json = await self._vault.get(key, collection=self._coll)
        if record_json:
            return ProviderClientRecord.model_validate_json(record_json)
        return None

    async def _save_provider_client_credentials(self, record: ProviderClientRecord) -> None:
        key = build_store_key(identity=self._identity, provider=record.provider, record_type="client")
        await self._vault.put(key, record.model_dump_json(), collection=self._coll)

    async def _update_provider_metadata(self, provider: str, connection_name: str) -> None:
        meta_key = build_store_key(identity=self._identity, provider=provider, record_type="metadata")
        existing_json = await self._vault.get(meta_key, collection=self._coll)
        if existing_json:
            metadata = ProviderMetadataRecord.model_validate_json(existing_json)
        else:
            metadata = ProviderMetadataRecord(identity=self._identity, provider=provider)
        if connection_name not in metadata.connection_names:
            metadata.connection_names.append(connection_name)
        metadata.last_used_connection = connection_name
        await self._vault.put(meta_key, metadata.model_dump_json(), collection=self._coll)

    async def _remove_from_provider_metadata(self, provider: str, connection_name: str) -> None:
        meta_key = build_store_key(identity=self._identity, provider=provider, record_type="metadata")
        existing_json = await self._vault.get(meta_key, collection=self._coll)
        if existing_json:
            metadata = ProviderMetadataRecord.model_validate_json(existing_json)
            if connection_name in metadata.connection_names:
                metadata.connection_names.remove(connection_name)
            if metadata.last_used_connection == connection_name:
                metadata.last_used_connection = metadata.connection_names[0] if metadata.connection_names else None
            await self._vault.put(meta_key, metadata.model_dump_json(), collection=self._coll)

    def _get_api_key(self, record: ConnectionRecord) -> str:
        if record.api_key is None:
            raise CredentialMissingError("No API key stored in connection record", provider=record.provider)
        return record.api_key

    async def _get_oauth_token(self, record: ConnectionRecord, provider: str, connection: str) -> str:
        if record.access_token is None:
            raise CredentialMissingError("No access token stored", provider=provider)

        now = utc_now()
        if record.expires_at:
            near_expiry = record.expires_at - timedelta(seconds=_NEAR_EXPIRY_SECONDS)
            if now < near_expiry:
                return record.access_token

            if record.refresh_token:
                try:
                    refreshed = await self._refresh_token(record, provider)
                    if refreshed.access_token is None:
                        raise RefreshFailedError("Refreshed record missing access token", provider=provider)
                    return refreshed.access_token
                except RefreshFailedError as exc:
                    fallback_available = record.expires_at and now < record.expires_at
                    audit.log(
                        "refresh_failed",
                        provider=provider,
                        connection=connection,
                        identity=self._identity,
                        error=str(exc),
                        fallback_available=bool(fallback_available),
                    )

                    if record.expires_at:
                        duration_secs = int((record.expires_at - now).total_seconds())
                        time_desc = format_duration(max(0, duration_secs))
                        if fallback_available:
                            msg = (
                                f"Warning: token refresh failed for {provider}/{connection} "
                                f"— using existing token (expires in {time_desc}). Re-authenticate soon."
                            )
                        else:
                            msg = (
                                f"Warning: token refresh failed for {provider}/{connection} "
                                f"— token expired {time_desc} ago. Re-authenticate soon."
                            )
                    else:
                        msg = f"Warning: token refresh failed for {provider}/{connection}. Re-authenticate soon."

                    logger.warning(msg)

                    if fallback_available:
                        return record.access_token

                    record.status = ConnectionStatus.EXPIRED
                    await self._save_connection(record)
                    raise
            else:
                if now >= record.expires_at:
                    record.status = ConnectionStatus.EXPIRED
                    await self._save_connection(record)
                    raise TokenExpiredError(provider=provider)
                return record.access_token
        else:
            return record.access_token

    async def _refresh_token(self, record: ConnectionRecord, provider_name: str) -> ConnectionRecord:
        definition = await self.get_provider(provider_name)
        state_record = await self._get_or_create_provider_state(provider_name)

        client_record = await self._get_provider_client_credentials(provider_name)
        client_id = client_record.client_id if client_record else None
        client_secret = client_record.client_secret if client_record else None
        base_url = record.base_url or (client_record.base_url if client_record else None)
        resolved_definition = definition.resolve_urls(base_url)

        handler_cls = _FLOW_HANDLERS.get(definition.flow)
        if handler_cls is None:
            raise RefreshFailedError(f"Unsupported flow type: {definition.flow}", provider=provider_name)

        handler = handler_cls()
        try:
            record = handler.refresh(
                provider=resolved_definition,
                record=record,
                client_id=client_id,
                client_secret=client_secret,
            )
        except Exception as exc:
            state_record.last_refresh_at = utc_now()
            state_record.last_refresh_error = str(exc)
            await self._save_provider_state(state_record)
            if isinstance(exc, RefreshFailedError):
                raise
            raise RefreshFailedError(str(exc), provider=provider_name) from exc

        await self._save_connection(record)

        now = utc_now()
        state_record.last_refresh_at = now
        state_record.last_refresh_error = None
        await self._save_provider_state(state_record)

        logger.info("Token refreshed: provider={}", provider_name)
        return record

    async def _get_or_create_provider_state(self, provider: str) -> ProviderStateRecord:
        key = build_store_key(identity=self._identity, provider=provider, record_type="state")
        existing = await self._vault.get(key, collection=self._coll)
        if existing:
            return ProviderStateRecord.model_validate_json(existing)
        return ProviderStateRecord(provider=provider, identity=self._identity)

    async def _save_provider_state(self, state: ProviderStateRecord) -> None:
        key = build_store_key(identity=self._identity, provider=state.provider, record_type="state")
        await self._vault.put(key, state.model_dump_json(), collection=self._coll)

    async def _get_access_token_from_record(self, record: ConnectionRecord) -> str:
        if record.auth_type == AuthType.API_KEY:
            return self._get_api_key(record)
        if record.auth_type == AuthType.OAUTH2:
            return await self._get_oauth_token(record, record.provider, record.connection_name)
        raise CredentialMissingError(f"Unsupported auth type: {record.auth_type}", provider=record.provider)

    async def _get_auth_headers_from_record(
        self, record: ConnectionRecord, definition: ProviderDefinition
    ) -> dict[str, str]:
        token = await self._get_access_token_from_record(record)

        if record.auth_type == AuthType.OAUTH2:
            return {"Authorization": f"Bearer {token}"}

        if record.auth_type == AuthType.API_KEY:
            if definition.api_key:
                header_name = definition.api_key.header_name
                prefix = definition.api_key.header_prefix
                if prefix:
                    return {header_name: f"{prefix} {token}"}
                return {header_name: token}
            return {"Authorization": f"Bearer {token}"}

        raise CredentialMissingError(
            f"Cannot build headers for auth type: {record.auth_type}", provider=record.provider
        )
