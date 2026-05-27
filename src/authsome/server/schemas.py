"""Server request and response schemas.

These are HTTP boundary models. They intentionally avoid exposing internal
auth/vault models directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    mode: Literal["local", "hosted"] = "local"
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


class ProviderRoute(BaseModel):
    provider: str
    connection: str | None = None
    api_url: str
    auth_endpoint_paths: list[str] = Field(default_factory=list)


class ProxyRoutesResponse(BaseModel):
    routes: list[ProviderRoute]
