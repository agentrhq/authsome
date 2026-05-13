"""DCR + PKCE OAuth2 flow."""

from __future__ import annotations

import json
import urllib.parse
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import requests as http_client

from authsome.auth.flows.base import AuthFlow, FlowResult
from authsome.auth.flows.oauth2_client import create_pkce_authorization, exchange_authorization_code
from authsome.auth.models.connection import AccountInfo, ConnectionRecord, ProviderClientRecord
from authsome.auth.models.enums import AuthType, ConnectionStatus
from authsome.auth.models.provider import ProviderDefinition
from authsome.auth.utils import resolve_callback_url
from authsome.errors import AuthenticationFailedError, DiscoveryError
from authsome.utils import utc_now

if TYPE_CHECKING:
    from authsome.auth.sessions import AuthSession


class DcrPkceFlow(AuthFlow):
    """Dynamic Client Registration + PKCE authorization code flow."""

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

        effective_scopes = scopes or provider.oauth.scopes or []

        redirect_uri = resolve_callback_url(runtime_session)

        registered_new_client = not client_id
        if registered_new_client:
            client_id, client_secret = await self._register_client(provider, effective_scopes, redirect_uri)

        assert client_id is not None  # guaranteed: either passed in or registered above

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
        if registered_new_client:
            runtime_session.payload["internal_client_id"] = client_id
            if client_secret:
                runtime_session.payload["internal_client_secret"] = client_secret

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

        # If DCR registered a client, it's stored in payload
        if "internal_client_id" in runtime_session.payload:
            client_id = runtime_session.payload["internal_client_id"]
            client_secret = runtime_session.payload.get("internal_client_secret")
            registered_new_client = True
        else:
            registered_new_client = False

        if not client_id:
            raise AuthenticationFailedError("DCR PKCE flow requires a client_id.", provider=provider.name)

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

        dcr_client = (
            ProviderClientRecord(
                schema_version=2,
                profile=profile,
                provider=provider.name,
                client_id=client_id,
                client_secret=client_secret,
            )
            if registered_new_client
            else None
        )
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
                metadata={"callback_handled_by": "runtime"},
            ),
            client_record=dcr_client,
        )

    async def _discover_registration_endpoint(self, provider: ProviderDefinition) -> str:
        if provider.oauth is None:
            raise DiscoveryError("No OAuth config", provider=provider.name)
        parsed = urllib.parse.urlparse(provider.oauth.authorization_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        for url in [
            f"{base_url}/.well-known/openid-configuration",
            f"{base_url}/.well-known/oauth-authorization-server",
        ]:
            try:
                resp = http_client.get(url, timeout=15)
                if resp.status_code == 200:
                    reg_endpoint = resp.json().get("registration_endpoint")
                    if reg_endpoint:
                        return reg_endpoint
            except (http_client.RequestException, json.JSONDecodeError):
                continue
        raise DiscoveryError(
            "Could not discover registration_endpoint via .well-known. "
            "Set registration.registration_endpoint in the provider definition.",
            provider=provider.name,
        )

    async def _register_client(
        self, provider: ProviderDefinition, scopes: list[str], redirect_uri: str
    ) -> tuple[str, str | None]:
        if provider.oauth is None:
            raise AuthenticationFailedError("No OAuth config", provider=provider.name)
        reg_endpoint = (
            provider.registration.registration_endpoint if provider.registration else None
        ) or await self._discover_registration_endpoint(provider)
        dcr_payload: dict[str, Any] = {
            "client_name": f"authsome-{provider.name}",
            "redirect_uris": [redirect_uri],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "client_secret_post",
            "code_challenge_methods_supported": ["S256"],
        }
        if scopes:
            dcr_payload["scope"] = " ".join(scopes)

        try:
            resp = http_client.post(
                reg_endpoint, json=dcr_payload, headers={"Content-Type": "application/json"}, timeout=30
            )
            resp.raise_for_status()
            reg_data = resp.json()
        except http_client.RequestException as exc:
            raise AuthenticationFailedError(
                f"Dynamic Client Registration failed: {exc}", provider=provider.name
            ) from exc
        except json.JSONDecodeError as exc:
            raise AuthenticationFailedError("DCR response was not valid JSON", provider=provider.name) from exc

        client_id = reg_data.get("client_id")
        if not client_id:
            raise AuthenticationFailedError("DCR response missing client_id", provider=provider.name)
        return client_id, reg_data.get("client_secret")
