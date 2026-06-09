"""Shared utility functions for the auth module."""

import hashlib
import re
import secrets
from base64 import urlsafe_b64encode
from urllib.parse import urlsplit, urlunsplit

from authsome.auth.input_provider import InputField
from authsome.auth.models.connection import ProviderClientRecord
from authsome.auth.models.enums import AuthType, FlowType
from authsome.auth.models.provider import ProviderDefinition
from authsome.auth.sessions import AuthSession
from authsome.errors import InvalidProviderSchemaError
from authsome.utils import is_filesystem_safe


def generate_pkce() -> tuple[str, str]:
    """Generate code verifier and challenge for PKCE."""
    code_verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


def resolve_callback_url(runtime_session: AuthSession) -> str:
    """Return the callback URL injected into the session by the server."""
    return str(runtime_session.payload.get("callback_url_override", ""))


def normalize_scopes(scopes: list[str] | None) -> set[str]:
    """Normalize a list of scopes into a set of cleaned strings."""
    return {scope.strip() for scope in scopes or [] if scope.strip()}


def normalize_base_url(base_url: str | None) -> str | None:
    """Normalize a base URL, enforcing lowercase scheme and host, and removing trailing slash."""
    if not base_url:
        return None
    raw = base_url.strip().rstrip("/")
    parsed = urlsplit(raw)
    if not parsed.scheme or not parsed.netloc:
        return raw
    return urlunsplit(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            parsed.query,
            parsed.fragment,
        )
    )


def export_name_part(value: str) -> str:
    """Convert a string into a component suitable for an environment variable name."""
    return re.sub(r"[^A-Z0-9]+", "_", value.upper()).strip("_")


VALID_FLOWS: dict[AuthType, set[FlowType]] = {
    AuthType.OAUTH2: {FlowType.PKCE, FlowType.DEVICE_CODE, FlowType.DCR_PKCE},
    AuthType.API_KEY: {FlowType.API_KEY},
    AuthType.BROWSER: {FlowType.BROWSER},
}


def validate_provider_definition(definition: ProviderDefinition) -> None:
    if not is_filesystem_safe(definition.name):
        raise InvalidProviderSchemaError(
            f"Provider name '{definition.name}' is not filesystem-safe",
            provider=definition.name,
        )
    valid_flows = VALID_FLOWS.get(definition.auth_type)
    if valid_flows is None:
        raise InvalidProviderSchemaError(
            f"Unrecognized auth_type: {definition.auth_type}",
            provider=definition.name,
        )
    if definition.flow not in valid_flows:
        raise InvalidProviderSchemaError(
            f"Flow '{definition.flow}' is not valid for auth_type '{definition.auth_type}'. "
            f"Valid flows: {[flow.value for flow in valid_flows]}",
            provider=definition.name,
        )
    if definition.auth_type == AuthType.OAUTH2 and definition.oauth is None:
        raise InvalidProviderSchemaError(
            "auth_type 'oauth2' requires an 'oauth' configuration section",
            provider=definition.name,
        )
    if definition.auth_type == AuthType.API_KEY and definition.api_key is None:
        raise InvalidProviderSchemaError(
            "auth_type 'api_key' requires an 'api_key' configuration section",
            provider=definition.name,
        )
    if definition.auth_type == AuthType.BROWSER and definition.browser is None:
        raise InvalidProviderSchemaError(
            "auth_type 'browser' requires a 'browser' configuration section",
            provider=definition.name,
        )


def required_inputs(  # noqa: PLR0913
    *,
    provider: ProviderDefinition,
    flow_type: FlowType,
    client_record: ProviderClientRecord | None,
    scopes: list[str] | None = None,
    base_url: str | None = None,
    provider_config_only: bool = False,
) -> list[InputField]:
    flow_base_url = base_url or (client_record.base_url if client_record else None)
    flow_client_id = client_record.client_id if client_record else None
    persisted_scopes = client_record.scopes if client_record else None
    fields: list[InputField] = []

    if provider.oauth and provider.oauth.base_url and (provider_config_only or not flow_base_url):
        fields.append(
            InputField(
                name="base_url",
                label="Base URL",
                secret=False,
                default=flow_base_url or provider.oauth.base_url,
            )
        )
        fields.append(
            InputField(
                name="api_url",
                label="API Host URL",
                secret=False,
                default=(
                    client_record.api_url
                    if client_record and client_record.api_url
                    else provider.primary_api_url() or ""
                ),
            )
        )

    if flow_type == FlowType.PKCE and (provider_config_only or not flow_client_id):
        fields.append(InputField(name="client_id", label="Client ID", secret=False, default=flow_client_id or ""))
        fields.append(
            InputField(
                name="client_secret",
                label="Client Secret",
                secret=True,
                default=client_record.client_secret if provider_config_only and client_record else "",
            )
        )
    elif flow_type == FlowType.DEVICE_CODE and (provider_config_only or not flow_client_id):
        fields.append(InputField(name="client_id", label="Client ID", secret=False, default=flow_client_id or ""))
        fields.append(
            InputField(
                name="client_secret",
                label="Client Secret (Optional)",
                secret=True,
                default=client_record.client_secret if provider_config_only and client_record else "",
            )
        )

    needs_scopes = flow_type in (FlowType.PKCE, FlowType.DEVICE_CODE, FlowType.DCR_PKCE)

    if needs_scopes and (provider_config_only or (scopes is None and persisted_scopes is None)):
        configured_scopes = (
            persisted_scopes
            if provider_config_only and persisted_scopes is not None
            else (provider.oauth.scopes if provider.oauth else [])
        )
        default_scopes = ",".join(configured_scopes)
        fields.append(
            InputField(
                name="scopes",
                label="Scopes (comma-separated)",
                secret=False,
                default=default_scopes,
                required=False,
            )
        )

    if flow_type == FlowType.API_KEY:
        api_key_field = InputField(name="api_key", label="API Key", secret=True)
        if provider.api_key and provider.api_key.key_pattern:
            api_key_field.pattern = provider.api_key.key_pattern
            api_key_field.pattern_hint = provider.api_key.key_pattern_hint
        fields.append(api_key_field)

    return fields
