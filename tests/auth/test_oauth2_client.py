"""Tests for Authlib-backed OAuth2 flow helpers."""

from __future__ import annotations

import urllib.parse
from typing import Any

import pytest
from requests import Session

from authsome.auth.flows.oauth2_client import (
    create_pkce_authorization,
    exchange_authorization_code,
    refresh_oauth_token,
    revoke_oauth_token,
)
from authsome.auth.flows.pkce import PkceFlow
from authsome.auth.models.enums import AuthType, FlowType
from authsome.auth.models.provider import OAuthConfig, ProviderDefinition
from authsome.errors import AuthenticationFailedError


class _TokenResponse:
    status_code = 200

    def json(self) -> dict[str, Any]:
        return {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
        }


def _make_oauth_provider() -> ProviderDefinition:
    return ProviderDefinition(
        name="oauth-test",
        display_name="OAuth Test",
        auth_type=AuthType.OAUTH2,
        flow=FlowType.PKCE,
        oauth=OAuthConfig(
            authorization_url="https://example.com/oauth/authorize",
            token_url="https://example.com/oauth/token",
            revocation_url="https://example.com/oauth/revoke",
            scopes=["read"],
        ),
    )


def test_create_pkce_authorization_uses_authlib_pkce_params() -> None:
    provider = _make_oauth_provider()

    auth_url, state, code_verifier = create_pkce_authorization(
        provider=provider,
        client_id="client-id",
        client_secret=None,
        redirect_uri="http://127.0.0.1:7999/auth/callback",
        scopes=["read", "write"],
    )

    parsed = urllib.parse.urlsplit(auth_url)
    params = urllib.parse.parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "example.com"
    assert parsed.path == "/oauth/authorize"
    assert params["client_id"] == ["client-id"]
    assert params["scope"] == ["read write"]
    assert params["state"] == [state]
    assert params["code_challenge_method"] == ["S256"]
    assert params["code_challenge"][0]
    assert code_verifier


def test_exchange_authorization_code_uses_authlib_token_request(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _make_oauth_provider()
    captured: dict[str, Any] = {}

    def fake_post(self: Session, url: str, data: dict[str, str], **kwargs: Any) -> _TokenResponse:
        captured["url"] = url
        captured["data"] = data
        captured["headers"] = kwargs.get("headers")
        captured["auth"] = kwargs.get("auth")
        return _TokenResponse()

    monkeypatch.setattr(Session, "post", fake_post)

    token = exchange_authorization_code(
        provider=provider,
        auth_code="auth-code",
        expected_state="expected-state",
        returned_state="expected-state",
        redirect_uri="http://127.0.0.1:7999/auth/callback",
        client_id="client-id",
        client_secret=None,
        code_verifier="verifier",
    )

    assert token["access_token"] == "access-token"
    assert captured["url"] == "https://example.com/oauth/token"
    assert captured["data"]["grant_type"] == "authorization_code"
    assert captured["data"]["code"] == "auth-code"
    assert captured["data"]["code_verifier"] == "verifier"
    assert captured["auth"] is not None


def test_exchange_authorization_code_rejects_state_mismatch() -> None:
    provider = _make_oauth_provider()

    with pytest.raises(AuthenticationFailedError, match="Token exchange failed"):
        exchange_authorization_code(
            provider=provider,
            auth_code="auth-code",
            expected_state="expected-state",
            returned_state="wrong-state",
            redirect_uri="http://127.0.0.1:7999/auth/callback",
            client_id="client-id",
            client_secret=None,
            code_verifier="verifier",
        )


def test_refresh_oauth_token_uses_authlib_refresh_request(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _make_oauth_provider()
    captured: dict[str, Any] = {}

    def fake_post(self: Session, url: str, data: dict[str, str], **kwargs: Any) -> _TokenResponse:
        captured["url"] = url
        captured["data"] = data
        captured["auth"] = kwargs.get("auth")
        return _TokenResponse()

    monkeypatch.setattr(Session, "post", fake_post)

    token = refresh_oauth_token(
        provider=provider,
        refresh_token="old-refresh-token",
        client_id="client-id",
        client_secret="client-secret",
    )

    assert token["access_token"] == "access-token"
    assert captured["url"] == "https://example.com/oauth/token"
    assert captured["data"]["grant_type"] == "refresh_token"
    assert captured["data"]["refresh_token"] == "old-refresh-token"
    assert captured["auth"] is not None


def test_revoke_oauth_token_uses_authlib_revocation_request(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = _make_oauth_provider()
    captured: dict[str, Any] = {}

    def fake_post(self: Session, url: str, data: dict[str, str], **kwargs: Any) -> _TokenResponse:
        captured["url"] = url
        captured["data"] = data
        captured["auth"] = kwargs.get("auth")
        return _TokenResponse()

    monkeypatch.setattr(Session, "post", fake_post)

    revoke_oauth_token(
        provider=provider,
        token="access-token",
        token_type_hint="access_token",
        client_id="client-id",
        client_secret="client-secret",
    )

    assert captured["url"] == "https://example.com/oauth/revoke"
    assert captured["data"]["token"] == "access-token"
    assert captured["data"]["token_type_hint"] == "access_token"
    assert captured["auth"] is not None


@pytest.mark.asyncio
async def test_pkce_flow_begin_stores_authlib_authorization_state() -> None:
    from unittest.mock import Mock

    provider = _make_oauth_provider()
    session = Mock()
    session.payload = {}

    await PkceFlow().begin(
        provider=provider,
        profile="default",
        connection_name="default",
        runtime_session=session,
        client_id="client-id",
    )

    assert session.state == "waiting_for_user"
    assert session.payload["auth_url"].startswith("https://example.com/oauth/authorize?")
    assert session.payload["internal_state"]
    assert session.payload["internal_code_verifier"]
