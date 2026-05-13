"""OAuth2 PKCE authorization code flow."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from authsome.auth.flows.base import AuthFlow, FlowResult
from authsome.auth.flows.oauth2_client import create_pkce_authorization, exchange_authorization_code
from authsome.auth.models.connection import AccountInfo, ConnectionRecord
from authsome.auth.models.enums import AuthType, ConnectionStatus
from authsome.auth.models.provider import ProviderDefinition
from authsome.auth.utils import resolve_callback_url
from authsome.errors import AuthenticationFailedError
from authsome.utils import utc_now

if TYPE_CHECKING:
    from authsome.auth.sessions import AuthSession


class PkceFlow(AuthFlow):
    """OAuth2 PKCE authorization code flow."""

    callback_port: int = 7999

    async def begin(
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

        redirect_uri = resolve_callback_url(runtime_session)

        auth_url, state, code_verifier = create_pkce_authorization(
            provider=provider,
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scopes=effective_scopes,
        )

        runtime_session.state = "waiting_for_user"
        runtime_session.payload["auth_url"] = auth_url
        runtime_session.payload["callback_url"] = redirect_uri
        runtime_session.payload["internal_code_verifier"] = code_verifier
        runtime_session.payload["internal_state"] = state
        runtime_session.payload["internal_scopes"] = json.dumps(effective_scopes)

    async def resume(
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

        returned_state = callback_data.get("state", "")
        expected_state = runtime_session.payload.get("internal_state")
        if not expected_state:
            raise AuthenticationFailedError("OAuth state missing from session", provider=provider.name)

        code_verifier = runtime_session.payload.get("internal_code_verifier", "")
        redirect_uri = runtime_session.payload.get("callback_url", "")
        effective_scopes = json.loads(runtime_session.payload.get("internal_scopes", "[]"))

        token_data = exchange_authorization_code(
            provider=provider,
            auth_code=auth_code,
            expected_state=expected_state,
            returned_state=returned_state,
            redirect_uri=redirect_uri,
            client_id=client_id,
            client_secret=client_secret,
            code_verifier=code_verifier,
        )

        runtime_session.state = "processing"

        now = utc_now()
        expires_in = token_data.get("expires_in")

        metadata: dict[str, str] = {"callback_handled_by": "runtime"}

        return FlowResult(
            connection=ConnectionRecord(
                schema_version=2,
                provider=provider.name,
                profile=profile,
                connection_name=connection_name,
                auth_type=AuthType.OAUTH2,
                status=ConnectionStatus.CONNECTED,
                scopes=effective_scopes,
                access_token=token_data.get("access_token", ""),
                refresh_token=token_data.get("refresh_token"),
                token_type=token_data.get("token_type", "Bearer"),
                expires_at=now + timedelta(seconds=int(expires_in)) if expires_in else None,
                obtained_at=now,
                account=AccountInfo(),
                metadata=metadata,
            )
        )
