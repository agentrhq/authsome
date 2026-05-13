"""Small Authlib-backed helpers for OAuth2 client flows."""

from __future__ import annotations

import urllib.parse
from typing import Any

import requests as http_client
from authlib.common.security import generate_token
from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.requests_client import OAuth2Session
from authlib.oauth2 import OAuth2Error

from authsome.auth.models.provider import ProviderDefinition
from authsome.errors import AuthenticationFailedError, RefreshFailedError

_PKCE_VERIFIER_LENGTH = 64
_DEVICE_CODE_GRANT = "urn:ietf:params:oauth:grant-type:device_code"


def create_pkce_authorization(
    *,
    provider: ProviderDefinition,
    client_id: str,
    client_secret: str | None,
    redirect_uri: str,
    scopes: list[str],
) -> tuple[str, str, str]:
    """Create an authorization URL and state using Authlib's PKCE support."""
    assert provider.oauth is not None

    session = OAuth2Session(
        client_id=client_id,
        client_secret=client_secret,
        scope=" ".join(scopes) if scopes else None,
        redirect_uri=redirect_uri,
        code_challenge_method="S256",
        token_endpoint_auth_method=_token_endpoint_auth_method(client_secret),
    )
    code_verifier = generate_token(_PKCE_VERIFIER_LENGTH)
    authorization_url, state = session.create_authorization_url(
        provider.oauth.authorization_url,
        code_verifier=code_verifier,
    )
    return authorization_url, state, code_verifier


def exchange_authorization_code(
    *,
    provider: ProviderDefinition,
    auth_code: str,
    expected_state: str,
    returned_state: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str | None,
    code_verifier: str,
) -> dict[str, Any]:
    """Exchange an authorization code for tokens using Authlib."""
    assert provider.oauth is not None

    session = OAuth2Session(
        client_id=client_id,
        client_secret=client_secret,
        state=expected_state,
        redirect_uri=redirect_uri,
        token_endpoint_auth_method=_token_endpoint_auth_method(client_secret),
    )
    authorization_response = _authorization_response_url(
        redirect_uri=redirect_uri,
        code=auth_code,
        state=returned_state,
    )

    try:
        token = session.fetch_token(
            provider.oauth.token_url,
            authorization_response=authorization_response,
            code_verifier=code_verifier,
            timeout=30,
        )
    except (OAuthError, OAuth2Error, http_client.RequestException, ValueError) as exc:
        raise AuthenticationFailedError(f"Token exchange failed: {exc}", provider=provider.name) from exc

    if "access_token" not in token:
        error = token.get("error", "")
        error_desc = token.get("error_description", "Unknown error")
        raise AuthenticationFailedError(f"Token exchange error: {error} - {error_desc}", provider=provider.name)

    return dict(token)


def refresh_oauth_token(
    *,
    provider: ProviderDefinition,
    refresh_token: str,
    client_id: str,
    client_secret: str | None,
) -> dict[str, Any]:
    """Refresh an OAuth access token using Authlib."""
    assert provider.oauth is not None

    session = OAuth2Session(
        client_id=client_id,
        client_secret=client_secret,
        token_endpoint_auth_method=_token_endpoint_auth_method(client_secret),
    )
    try:
        token = session.refresh_token(
            provider.oauth.token_url,
            refresh_token=refresh_token,
            timeout=30,
        )
    except (OAuthError, OAuth2Error, http_client.RequestException, ValueError) as exc:
        raise RefreshFailedError(f"Token refresh failed: {exc}", provider=provider.name) from exc

    return dict(token)


def revoke_oauth_token(
    *,
    provider: ProviderDefinition,
    token: str,
    token_type_hint: str,
    client_id: str | None,
    client_secret: str | None,
) -> None:
    """Revoke an OAuth token using Authlib."""
    assert provider.oauth is not None
    assert provider.oauth.revocation_url is not None

    session = OAuth2Session(
        client_id=client_id,
        client_secret=client_secret,
        revocation_endpoint_auth_method=_token_endpoint_auth_method(client_secret),
    )
    session.revoke_token(
        provider.oauth.revocation_url,
        token=token,
        token_type_hint=token_type_hint,
        timeout=15,
    )


def fetch_device_token(
    *,
    provider: ProviderDefinition,
    device_code: str,
    client_id: str | None,
    client_secret: str | None,
) -> dict[str, Any]:
    """Poll a device-code token endpoint once using Authlib response handling."""
    assert provider.oauth is not None

    session = OAuth2Session(
        client_id=client_id,
        client_secret=client_secret,
        token_endpoint_auth_method=_token_endpoint_auth_method(client_secret),
    )

    if provider.oauth.device_token_request == "json":
        response = http_client.post(
            provider.oauth.token_url,
            json={"device_code": device_code},
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=30,
        )
        return dict(session.parse_response_token(response))

    token = session.fetch_token(
        provider.oauth.token_url,
        grant_type=_DEVICE_CODE_GRANT,
        device_code=device_code,
        timeout=30,
    )
    return dict(token)


def _token_endpoint_auth_method(client_secret: str | None) -> str:
    return "client_secret_post" if client_secret else "none"


def _authorization_response_url(*, redirect_uri: str, code: str, state: str) -> str:
    parsed = urllib.parse.urlsplit(redirect_uri)
    query = urllib.parse.urlencode({"code": code, "state": state})
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))
