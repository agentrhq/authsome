"""AuthService — authentication and credential lifecycle service.

Owns OAuth flows, token refresh, login/logout/revoke.
Lives in server/ because it coordinates auth/ flows with vault/ storage and audit/ logging.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any
from urllib.parse import urlparse

from loguru import logger

from authsome import audit
from authsome.auth.flows.api_key import ApiKeyFlow
from authsome.auth.flows.browser import BrowserFlow
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
from authsome.auth.utils import (
    export_name_part,
    normalize_base_url,
    normalize_scopes,
    required_inputs,
    validate_provider_definition,
)
from authsome.errors import (
    ConnectionNotFoundError,
    CredentialMissingError,
    IdentityNotFoundError,
    InvalidProviderSchemaError,
    OperationNotAllowedError,
    RefreshFailedError,
    TokenExpiredError,
    UnsupportedFlowError,
)
from authsome.identity.principal import PrincipalRole
from authsome.server.credential_repository import CredentialRepository, parse_store_key
from authsome.server.provider_repository import ProviderRepository
from authsome.utils import format_duration, utc_now
from authsome.vault import Vault

_NEAR_EXPIRY_SECONDS = 300

_FLOW_HANDLERS = {
    FlowType.PKCE: PkceFlow,
    FlowType.DEVICE_CODE: DeviceCodeFlow,
    FlowType.DCR_PKCE: DcrPkceFlow,
    FlowType.API_KEY: ApiKeyFlow,
    FlowType.BROWSER: BrowserFlow,
}


class AuthService:
    """
    Authentication and credential lifecycle service.

    Coordinates provider lookup, auth flows, credential persistence, and policy checks.
    """

    def __init__(
        self,
        *,
        credentials: CredentialRepository,
        providers: ProviderRepository,
        identity: str | None = None,
        principal_id: str | None = None,
        principal_role: PrincipalRole = PrincipalRole.USER,
        vault_id: str | None = None,
    ) -> None:
        self._credentials = credentials
        self._identity = identity
        self._principal_id = principal_id
        self._vault_id = vault_id or credentials.vault_id
        self._principal_role = principal_role
        self._providers = providers

    @property
    def vault(self) -> Vault:
        return self._credentials.vault

    @property
    def identity(self) -> str | None:
        return self._identity

    def require_identity(self) -> str:
        """Return the PoP-authenticated identity handle for identity-scoped routes."""
        if self._identity is None:
            raise ValueError("AuthService identity is required for this operation")
        return self._identity

    @property
    def principal_id(self) -> str | None:
        return self._principal_id

    @property
    def principal_role(self) -> PrincipalRole:
        return self._principal_role

    @property
    def vault_id(self) -> str | None:
        return self._vault_id

    # ── Provider operations ───────────────────────────────────────────────

    async def list_providers(self) -> list[ProviderDefinition]:
        return await self._providers.list()

    async def list_providers_by_source(self) -> dict[str, list[ProviderDefinition]]:
        return await self._providers.list_by_source()

    async def get_provider(self, provider: str) -> ProviderDefinition:
        return await self._providers.get(provider)

    async def is_local_provider(self, provider: str) -> bool:
        """Check if a provider is a custom/local provider."""
        return await self._providers.is_custom(provider)

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
        self._ensure_admin_operation_allowed("register", definition.name)
        self._validate_provider(definition)
        await self._providers.save_custom(definition, force=force)
        logger.info("Registered provider: {}", definition.name)

    async def remove_provider(self, name: str) -> bool:
        """Remove a custom provider. Returns True if removed."""
        return await self._providers.delete_custom(name)

    def _ensure_admin_operation_allowed(self, operation: str, provider: str) -> None:
        if self._principal_role == PrincipalRole.ADMIN:
            return
        raise OperationNotAllowedError(
            operation,
            f"{operation} requires an admin principal",
            provider=provider,
        )

    def _ensure_provider_client_mutation_allowed(self, provider: str) -> None:
        if self._principal_role == PrincipalRole.ADMIN:
            return
        raise OperationNotAllowedError(
            "login",
            "provider client configuration requires an admin principal",
            provider=provider,
        )

    def _validate_provider(self, definition: ProviderDefinition) -> None:
        validate_provider_definition(definition)
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
        keys = await self._credentials.list_connection_keys()

        providers: dict[str, list[dict[str, Any]]] = {}
        defaults: dict[str, str] = {}
        for key in keys:
            parts = parse_store_key(key)
            if parts.record_type == "connection" and parts.provider and parts.connection:
                provider_name = parts.provider
                connection_name = parts.connection
                if provider_name not in defaults:
                    metadata = await self._credentials.get_provider_metadata(provider_name)
                    defaults[provider_name] = metadata.default_connection if metadata else "default"
                record = await self._credentials.get_connection(provider_name, connection_name)
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
                        "api_url": record.api_url,
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
        record = await self._credentials.get_connection(provider, connection)
        if record is None:
            raise ConnectionNotFoundError(
                provider=provider,
                connection=connection,
                identity=self._identity or self._principal_id or "hosted-ui",
            )
        return record

    async def resolve_connection_name(self, provider: str, connection: str | None = None) -> str:
        """Resolve an optional connection name to the provider default."""
        if connection:
            return connection
        metadata = await self._credentials.get_provider_metadata(provider)
        return metadata.default_connection if metadata else "default"

    async def get_provider_client(self, provider: str) -> ProviderClientRecord | None:
        """Return stored client credentials for a provider, or None if absent.

        Public read-only accessor. The secret field is still stored encrypted at rest;
        callers are responsible for redacting before display.
        """
        return await self._get_provider_client_credentials(provider)

    async def update_provider_configuration(
        self,
        provider: str,
        inputs: dict[str, str],
        *,
        vault_ids: list[str] | None = None,
    ) -> bool:
        """Replace stored provider credentials and revoke connections when they change."""
        self._ensure_provider_client_mutation_allowed(provider)
        definition = await self.get_provider(provider)
        if definition.auth_type != AuthType.OAUTH2:
            return False

        existing = await self._get_provider_client_credentials(provider)
        refresh_dcr_client = definition.flow == FlowType.DCR_PKCE and existing is not None and "client_id" not in inputs
        updated = ProviderClientRecord(provider=provider)
        updated.client_id = (
            None if refresh_dcr_client else inputs.get("client_id", existing.client_id if existing else None) or None
        )

        if refresh_dcr_client:
            updated.client_secret = None
        elif "client_secret" in inputs:
            secret_input = inputs["client_secret"].strip()
            if secret_input:
                updated.client_secret = secret_input
            else:
                updated.client_secret = existing.client_secret if existing else None
        else:
            updated.client_secret = existing.client_secret if existing else None

        if definition.oauth and definition.oauth.base_url:
            updated.base_url = inputs.get("base_url", existing.base_url if existing else None) or None
            updated.api_url = inputs.get("api_url", existing.api_url if existing else None) or None
        else:
            updated.base_url = existing.base_url if existing else None
            updated.api_url = existing.api_url if existing else None

        if "scopes" in inputs:
            scopes_input = inputs["scopes"].strip()
            updated.scopes = [s.strip() for s in scopes_input.split(",") if s.strip()] if scopes_input else []
        elif existing and existing.scopes is not None:
            updated.scopes = list(existing.scopes)
        else:
            updated.scopes = list(definition.oauth.scopes or []) if definition.oauth else []
        updated.metadata = dict(existing.metadata) if existing else {}

        changed = existing is None or any(
            (
                existing.client_id != updated.client_id,
                existing.client_secret != updated.client_secret,
                existing.base_url != updated.base_url,
                existing.api_url != updated.api_url,
                existing.scopes != updated.scopes,
            )
        )
        if not changed:
            return False

        if existing is not None:
            await self.revoke(provider, vault_ids=vault_ids)
        await self._save_provider_client_credentials(updated)
        return True

    async def set_default_connection(self, provider: str, connection: str) -> None:
        """Set the default connection for a provider."""
        await self.get_connection(provider, connection)
        metadata = await self._credentials.get_provider_metadata(provider)
        if metadata is None:
            metadata = ProviderMetadataRecord(
                identity=self._identity,
                principal_id=self._principal_id,
                vault_id=self._vault_id,
                provider=provider,
            )
        if connection not in metadata.connection_names:
            metadata.connection_names.append(connection)
        metadata.default_connection = connection
        metadata.last_used_connection = connection
        await self._credentials.save_provider_metadata(metadata)

    # ── Authentication ────────────────────────────────────────────────────

    async def get_required_inputs(
        self,
        session: AuthSession,
        scopes: list[str] | None = None,
        base_url: str | None = None,
    ) -> list[InputField]:
        """Determine what inputs are missing for a given session."""
        provider = session.provider
        definition = await self.get_provider(provider)
        client_record = await self._get_provider_client_credentials(provider)
        return required_inputs(
            provider=definition,
            flow_type=FlowType(session.flow_type),
            client_record=client_record,
            scopes=scopes,
            base_url=base_url,
            provider_config_only=bool(session.payload.get("provider_config_only")),
        )

    async def save_inputs(self, session: AuthSession, inputs: dict[str, str]) -> None:
        """Save collected inputs to the Vault or session payload."""
        from authsome.auth.models.connection import ProviderClientRecord

        provider = session.provider
        flow_type = FlowType(session.flow_type)
        client_record = await self._get_provider_client_credentials(provider)

        if flow_type in (FlowType.PKCE, FlowType.DEVICE_CODE, FlowType.DCR_PKCE):
            if inputs:
                self._ensure_provider_client_mutation_allowed(provider)

            if client_record is None and inputs:
                client_record = ProviderClientRecord(provider=provider)

            if client_record is not None:
                if base_url := inputs.get("base_url"):
                    client_record.base_url = base_url
                    session.payload["base_url"] = base_url
                if api_url := inputs.get("api_url"):
                    client_record.api_url = api_url
                if client_id := inputs.get("client_id"):
                    client_record.client_id = client_id
                if client_secret := inputs.get("client_secret"):
                    client_record.client_secret = client_secret
                if "scopes" in inputs:
                    scopes_input = inputs["scopes"].strip()
                    client_record.scopes = (
                        [s.strip() for s in scopes_input.split(",") if s.strip()] if scopes_input else []
                    )

            if client_record is not None and inputs:
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
            self._ensure_provider_client_mutation_allowed(provider)
            if client_record is None:
                client_record = ProviderClientRecord(provider=provider)
            client_record.client_id = result.client_record.client_id
            client_record.client_secret = result.client_record.client_secret
            client_record.base_url = result.client_record.base_url or client_record.base_url
            await self._save_provider_client_credentials(client_record)

        result.connection.base_url = flow_base_url
        result.connection.api_url = client_record.api_url if client_record and client_record.api_url else None

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
        if not definition.docs_url:
            return []
        if flow_type not in (FlowType.PKCE, FlowType.DEVICE_CODE, FlowType.DCR_PKCE, FlowType.API_KEY):
            return []
        return [{"type": "instructions", "label": "Instructions", "url": definition.docs_url}]

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

        await self._credentials.delete_connection(provider, connection)
        await self._remove_from_provider_metadata(provider, connection)

    async def revoke(self, provider: str, vault_ids: list[str] | None = None) -> None:
        """Revoke all tokens for a provider across the given vault IDs.

        The server layer resolves the full list of vault IDs and passes them in.
        When vault_ids is None, only this service's own vault_id is used.
        """
        self._ensure_admin_operation_allowed("revoke", provider)
        await self.get_provider(provider)
        ids_to_revoke = vault_ids if vault_ids is not None else ([self._vault_id] if self._vault_id else [])
        for vault_id in ids_to_revoke:
            credentials = CredentialRepository(
                self.vault,
                identity=self._identity,
                principal_id=self._principal_id,
                vault_id=vault_id,
            )
            vault_service = AuthService(
                credentials=credentials,
                providers=self._providers,
                identity=self._identity,
                principal_id=self._principal_id,
                principal_role=self._principal_role,
                vault_id=vault_id,
            )
            metadata = await credentials.get_provider_metadata(provider)
            if metadata is None:
                continue

            for conn_name in list(metadata.connection_names):
                await vault_service.logout(provider, connection=conn_name)
            await credentials.delete_provider_metadata(provider)

        await self._credentials.delete_provider_client(provider)

    async def remove(self, provider: str) -> None:
        """Revoke all tokens and remove the provider definition if it is local."""
        self._ensure_admin_operation_allowed("remove", provider)
        await self.revoke(provider)
        if await self.is_local_provider(provider):
            await self._providers.delete_custom(provider)
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
        elif record.auth_type == AuthType.BROWSER:
            for k, v in (record.credentials or {}).items():
                env_name = export_map.get(k, f"{export_name_part(provider)}_{k.upper()}")
                values[env_name] = v

        if definition.export and definition.export.model_extra:
            token = record.access_token if record.auth_type == AuthType.OAUTH2 else record.api_key
            available_values = {
                "BASE_URL": record.base_url,
                "API_URL": record.api_url or definition.primary_api_url() or record.base_url,
                "ACCESS_TOKEN": token,
                "API_TOKEN": token,
            }

            for target_env, source_field in definition.export.model_extra.items():
                if isinstance(source_field, str) and (val := available_values.get(source_field.upper())):
                    values[target_env] = val

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
        return self.require_identity()

    # ── Internal helpers ──────────────────────────────────────────────────

    async def _save_connection(self, record: ConnectionRecord) -> None:
        await self._credentials.save_connection(record)

    async def _get_provider_client_credentials(self, provider: str) -> ProviderClientRecord | None:
        return await self._credentials.get_provider_client(provider)

    async def _save_provider_client_credentials(self, record: ProviderClientRecord) -> None:
        await self._credentials.save_provider_client(record)

    async def _update_provider_metadata(self, provider: str, connection_name: str) -> None:
        metadata = await self._credentials.get_provider_metadata(provider)
        if metadata is None:
            metadata = ProviderMetadataRecord(
                identity=self._identity,
                principal_id=self._principal_id,
                vault_id=self._vault_id,
                provider=provider,
            )
        if connection_name not in metadata.connection_names:
            metadata.connection_names.append(connection_name)
        metadata.last_used_connection = connection_name
        await self._credentials.save_provider_metadata(metadata)

    async def _remove_from_provider_metadata(self, provider: str, connection_name: str) -> None:
        metadata = await self._credentials.get_provider_metadata(provider)
        if metadata is None:
            return
        if connection_name in metadata.connection_names:
            metadata.connection_names.remove(connection_name)
        if metadata.last_used_connection == connection_name:
            metadata.last_used_connection = metadata.connection_names[0] if metadata.connection_names else None
        await self._credentials.save_provider_metadata(metadata)

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
                    audit.emit_event(
                        "refresh_failed",
                        provider=provider,
                        connection=connection,
                        identity=self._identity,
                        principal_id=self._principal_id,
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
        existing = await self._credentials.get_provider_state(provider)
        if existing:
            return existing
        return ProviderStateRecord(
            provider=provider,
            identity=self._identity,
            principal_id=self._principal_id,
            vault_id=self._vault_id,
        )

    async def _save_provider_state(self, state: ProviderStateRecord) -> None:
        await self._credentials.save_provider_state(state)

    async def _get_access_token_from_record(self, record: ConnectionRecord) -> str:
        if record.auth_type == AuthType.API_KEY:
            return self._get_api_key(record)
        if record.auth_type == AuthType.OAUTH2:
            return await self._get_oauth_token(record, record.provider, record.connection_name)
        raise CredentialMissingError(f"Unsupported auth type: {record.auth_type}", provider=record.provider)

    async def _get_auth_headers_from_record(
        self, record: ConnectionRecord, definition: ProviderDefinition
    ) -> dict[str, str]:
        if record.auth_type == AuthType.BROWSER:
            if not record.credentials:
                raise CredentialMissingError("No browser credentials stored", provider=record.provider)
            if record.expires_at and utc_now() >= record.expires_at:
                raise TokenExpiredError(provider=record.provider)
            cfg = definition.browser
            headers: dict[str, str] = {}
            if cfg:
                for rule in cfg.extract:
                    if v := record.credentials.get(rule.cookie):
                        headers[rule.header] = f"{rule.prefix}{v}" if rule.prefix else v
                headers.update(cfg.extra_headers)
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in record.credentials.items())
            return headers

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
