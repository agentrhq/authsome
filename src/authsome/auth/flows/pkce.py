"""OAuth2 PKCE authorization code flow."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import requests as http_client
from authlib.common.security import generate_token
from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.requests_client import OAuth2Session

from authsome.auth.flows.base import (
    DEFAULT_CALLBACK_URL,
    AuthFlow,
    FlowResult,
    token_to_connection_record,
)
from authsome.auth.models.provider import ProviderDefinition
from authsome.errors import AuthenticationFailedError

if TYPE_CHECKING:
    from authsome.auth.sessions import AuthSession


class PkceFlow(AuthFlow):
    """OAuth2 PKCE authorization code flow."""

    callback_port: int = 7999

    def begin(
        self,
        provider: ProviderDefinition,
        profile: str,
        connection_name: str,
        runtime_session: AuthSession,
        scopes: list[str] | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        base_url: str | None = None,
    ) -> None:
        if provider.oauth is None:
            raise AuthenticationFailedError("Provider missing 'oauth' configuration", provider=provider.name)
        if not client_id:
            raise AuthenticationFailedError("PKCE flow requires a client_id.", provider=provider.name)

        effective_scopes = scopes or provider.oauth.scopes or []
        redirect_uri = runtime_session.payload.get("callback_url_override") or DEFAULT_CALLBACK_URL
        code_verifier = generate_token(48)

        client = OAuth2Session(
            token_endpoint_auth_method="client_secret_post" if client_secret else "none",
            client_id=client_id,
            client_secret=client_secret,
            scope=" ".join(effective_scopes) if effective_scopes else None,
            redirect_uri=redirect_uri,
            code_challenge_method="S256",
        )
        auth_url, state = client.create_authorization_url(
            provider.oauth.authorization_url,
            code_verifier=code_verifier,
        )

        runtime_session.state = "waiting_for_user"
        runtime_session.payload["auth_url"] = auth_url
        runtime_session.payload["callback_url"] = redirect_uri
        runtime_session.payload["internal_code_verifier"] = code_verifier
        runtime_session.payload["internal_state"] = state
        runtime_session.payload["internal_scopes"] = json.dumps(effective_scopes)

    def resume(
        self,
        provider: ProviderDefinition,
        profile: str,
        connection_name: str,
        runtime_session: AuthSession,
        callback_data: dict[str, Any],
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> FlowResult:
        if provider.oauth is None:
            raise AuthenticationFailedError("Provider missing 'oauth' configuration", provider=provider.name)
        if not client_id:
            raise AuthenticationFailedError("PKCE flow requires a client_id.", provider=provider.name)

        error = callback_data.get("error")
        if error:
            raise AuthenticationFailedError(f"OAuth error: {error}", provider=provider.name)

        auth_code = callback_data.get("code")
        if not auth_code:
            raise AuthenticationFailedError("Authorization timed out or no code received", provider=provider.name)

        expected_state = runtime_session.payload.get("internal_state")
        if callback_data.get("state") != expected_state:
            raise AuthenticationFailedError("OAuth state mismatch — potential CSRF attack", provider=provider.name)

        code_verifier = runtime_session.payload.get("internal_code_verifier", "")
        redirect_uri = runtime_session.payload.get("callback_url", "")
        effective_scopes = json.loads(runtime_session.payload.get("internal_scopes", "[]"))

        client = OAuth2Session(
            token_endpoint_auth_method="client_secret_post" if client_secret else "none",
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
        )
        try:
            token = client.fetch_token(
                provider.oauth.token_url,
                grant_type="authorization_code",
                code=auth_code,
                code_verifier=code_verifier,
            )
        except OAuthError as exc:
            raise AuthenticationFailedError(
                f"Token exchange error: {exc.error} — {exc.description or 'Unknown error'}",
                provider=provider.name,
            ) from exc
        except http_client.RequestException as exc:
            raise AuthenticationFailedError(f"Token exchange failed: {exc}", provider=provider.name) from exc

        runtime_session.state = "processing"

        return FlowResult(
            connection=token_to_connection_record(
                dict(token),
                provider=provider.name,
                profile=profile,
                connection_name=connection_name,
                scopes=effective_scopes,
            )
        )
