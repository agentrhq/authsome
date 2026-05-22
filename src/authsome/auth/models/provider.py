"""Provider definition models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from authsome.auth.models.enums import AuthType, FlowType


class OAuthConfig(BaseModel):
    """OAuth2-specific provider configuration."""

    authorization_url: str
    token_url: str
    revocation_url: str | None = None
    device_authorization_url: str | None = None
    #: ``json`` = poll token URL with ``POST`` JSON body ``{"device_code": "..."}`` (e.g. Postiz CLI auth).
    device_token_request: Literal["oauth2_form", "json"] = "oauth2_form"
    scopes: list[str] = Field(default_factory=list)
    pkce: bool = True
    supports_device_code: bool = False
    supports_dcr: bool = False
    base_url: str | None = None

    model_config = {"extra": "allow"}


class ClientRegistrationConfig(BaseModel):
    """Dynamic Client Registration configuration."""

    registration_endpoint: str | None = None

    model_config = {"extra": "allow"}


class ApiKeyConfig(BaseModel):
    """API key provider configuration."""

    header_name: str = "Authorization"
    header_prefix: str | None = "Bearer"
    #: Optional regex (``re.fullmatch``) that valid keys must satisfy. When unset, no validation runs.
    key_pattern: str | None = None
    #: Optional human-readable hint shown when ``key_pattern`` does not match (e.g. "Keys start with 'sk-'.").
    key_pattern_hint: str | None = None

    model_config = {"extra": "allow"}


class ExportConfig(BaseModel):
    """Export mapping for environment variable names."""

    env: dict[str, str] = Field(default_factory=dict)

    model_config = {"extra": "allow"}


class ExtractRule(BaseModel):
    """One extraction rule: pull a named value out of cookies or localStorage."""

    from_: Literal["cookies", "localStorage"] = Field(alias="from")
    as_: str = Field(alias="as")
    match: str  # "*" = all cookies joined as "k=v; k=v"; exact name = single value
    json_path: str | None = Field(default=None, alias="jsonPath")

    model_config = {"populate_by_name": True, "extra": "allow"}


class BrowserSSOConfig(BaseModel):
    """Browser SSO provider configuration."""

    entry_url: str
    domains: list[str] = Field(min_length=1)
    validate_url: str | None = None
    extract: list[ExtractRule] = Field(min_length=1)
    extra_headers: dict[str, str] = Field(default_factory=dict)
    network_proxy: str | None = None
    ttl: str | None = None
    ttl_from_cookie: str | None = None  # cookie name whose expires timestamp overrides ttl
    login_mode: Literal["auto", "visible", "headless"] = "auto"
    # Override the Chrome/Chromium executable path (null = auto-detect).
    browser_exec: str | None = None
    # Override the browser profile directory (null = try real Chrome profile first,
    # then fall back to ~/.authsome/browser-data/).
    browser_data_dir: str | None = None

    model_config = {"extra": "allow"}


class ProviderDefinition(BaseModel):
    """
    Complete provider definition.

    Stored as JSON in providers/<name>.json.
    """

    schema_version: int = 1
    name: str
    display_name: str
    auth_type: AuthType
    flow: FlowType

    oauth: OAuthConfig | None = None
    registration: ClientRegistrationConfig | None = None
    api_key: ApiKeyConfig | None = None
    browser_sso: BrowserSSOConfig | None = None
    export: ExportConfig | None = None
    docs_url: str | None = None
    api_url: str | None = None

    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "allow"}

    def resolve_urls(self, base_url: str | None = None) -> ProviderDefinition:
        """Return a new ProviderDefinition with {base_url} templates resolved."""
        # Use provided base_url or fall back to the one in oauth config
        resolved_base_url = base_url or (self.oauth.base_url if self.oauth else None)
        if not resolved_base_url:
            return self

        # Create a copy
        resolved = self.model_copy(deep=True)

        def resolve(url: str | None) -> str | None:
            if url and "{base_url}" in url:
                return url.replace("{base_url}", resolved_base_url.rstrip("/"))
            return url

        # Resolve OAuth URLs
        if resolved.oauth:
            resolved.oauth.authorization_url = (
                resolve(resolved.oauth.authorization_url) or resolved.oauth.authorization_url
            )
            resolved.oauth.token_url = resolve(resolved.oauth.token_url) or resolved.oauth.token_url
            resolved.oauth.revocation_url = resolve(resolved.oauth.revocation_url)
            resolved.oauth.device_authorization_url = resolve(resolved.oauth.device_authorization_url)

        # Resolve Registration URLs
        if resolved.registration and resolved.registration.registration_endpoint:
            resolved.registration.registration_endpoint = resolve(resolved.registration.registration_endpoint)

        # Resolve api_url if it contains the template
        resolved.api_url = resolve(resolved.api_url) or resolved.api_url

        return resolved
