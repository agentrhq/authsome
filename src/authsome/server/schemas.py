"""Server request and response schemas.

These are HTTP boundary models. They intentionally avoid exposing internal
auth/vault models directly.
"""

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from authsome.utils import utc_now


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    configured_encryption_mode: str | None = None
    effective_encryption_source: str | None = None
    encryption_backend: str | None = None
    store_backend: str | None = None


class ReadyResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict[str, str] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    configured_encryption_mode: str | None = None
    effective_encryption_source: str | None = None
    encryption_backend: str | None = None


class OpenUrlAction(BaseModel):
    type: Literal["open_url"]
    url: str


class NoneAction(BaseModel):
    type: Literal["none"] = "none"


class BrowserAction(BaseModel):
    type: Literal["browser"] = "browser"
    entry_url: str
    domains: list[str]
    auth_cookies: list[str]
    ttl_from_cookie: str | None = None
    ttl_hours: int = 24


NextAction = Annotated[OpenUrlAction | BrowserAction | NoneAction, Field(discriminator="type")]


class AuthSessionResponse(BaseModel):
    id: str
    provider: str
    connection: str
    status: str
    message: str | None = None
    error: str | None = None
    created_at: datetime | None = None
    expires_at: datetime | None = None
    next_action: NextAction = Field(default_factory=NoneAction)
    user_code: str | None = None
    verification_uri: str | None = None
    verification_uri_complete: str | None = None


class UiBootstrapResponse(BaseModel):
    url: str


class StartAuthSessionRequest(BaseModel):
    provider: str
    connection: str = "default"
    flow: str | None = None
    scopes: list[str] | None = None
    base_url: str | None = None
    force: bool = False


class ResumeAuthSessionRequest(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class CredentialResolutionRequest(BaseModel):
    provider: str
    connection: str | None = None


class CredentialResolutionResponse(BaseModel):
    provider: str
    connection: str
    headers: dict[str, str]
    expires_at: datetime | None = None
    source: Literal["local", "global"]


class ProviderRoute(BaseModel):
    provider: str
    connection: str | None = None
    api_url: str
    auth_endpoint_paths: list[str] = Field(default_factory=list)


class ProxyRoutesResponse(BaseModel):
    routes: list[ProviderRoute]


class VaultRecord(BaseModel):
    """Vault record owned as a first-class server resource."""

    vault_id: str
    handle: str = "default"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class PrincipalVaultBindingRecord(BaseModel):
    """Server-owned binding from principal to vault."""

    principal_id: str
    vault_id: str
    is_default: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class GlobalProviderConnectionRecord(BaseModel):
    """Server-owned pointer to a vault-local connection used as a global fallback."""

    provider: str
    owner_principal_id: str
    owner_vault_id: str
    connection_name: str
    created_by_identity: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class ConnectionSummaryResponse(BaseModel):
    provider: str
    provider_display_name: str
    connection_name: str
    status: str
    auth_type: str
    account_label: str | None = None
    principal_id: str | None = None


class GlobalConnectionSummaryResponse(BaseModel):
    provider: str
    provider_display_name: str
    connection_name: str
    status: str
    auth_type: str
    account_label: str | None = None
    api_url: str | None = None
    source: Literal["global"] = "global"


class ProviderClientResponse(BaseModel):
    client_id: str | None = None
    client_secret: str | None = None
    base_url: str | None = None
    api_url: str | None = None
    scopes: list[str] = Field(default_factory=list)


class ProviderPrincipalUsageResponse(BaseModel):
    principal_id: str
    email: str | None = None
    connections: list[ConnectionSummaryResponse] = Field(default_factory=list)


class ProviderDetailResponse(BaseModel):
    provider: dict[str, Any]
    account: dict[str, Any]
    client: ProviderClientResponse | None = None
    configuration_fields: list[dict[str, Any]] = Field(default_factory=list)
    configuration_warning: str | None = None
    show_callback_helper: bool = False
    callback_url: str | None = None
    connections: list[ConnectionSummaryResponse] = Field(default_factory=list)
    principal_usage: list[ProviderPrincipalUsageResponse] = Field(default_factory=list)


class ProviderConfigurationUpdateRequest(BaseModel):
    client_id: str | None = None
    client_secret: str | None = None
    base_url: str | None = None
    api_url: str | None = None
    scopes: str | list[str] | None = None


class ProviderConfigurationUpdateResponse(BaseModel):
    status: Literal["ok"] = "ok"
    changed: bool
    provider: str


class ConnectionSecretsResponse(BaseModel):
    access_token: str | None = None
    refresh_token: str | None = None
    api_key: str | None = None
    credentials: dict[str, str] = Field(default_factory=dict)


class ConnectionDetailResponse(BaseModel):
    provider: str
    provider_display_name: str
    connection_name: str
    principal_id: str | None = None
    identity: str | None = None
    vault_id: str | None = None
    status: str
    auth_type: str
    base_url: str | None = None
    api_url: str | None = None
    scopes: list[str] = Field(default_factory=list)
    token_type: str | None = None
    obtained_at: datetime | None = None
    expires_at: datetime | None = None
    account: dict[str, Any] | None = None
    secrets: ConnectionSecretsResponse = Field(default_factory=ConnectionSecretsResponse)
    can_set_default: bool = False
    can_set_global: bool = False
    is_global: bool = False
