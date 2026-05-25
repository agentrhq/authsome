"""Abstract base class and result type for authentication flows."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import requests as http_client
from loguru import logger

from authsome.auth.models.connection import ConnectionRecord, ProviderClientRecord
from authsome.auth.models.enums import ConnectionStatus
from authsome.auth.models.provider import ProviderDefinition
from authsome.errors import RefreshFailedError
from authsome.utils import utc_now

if TYPE_CHECKING:
    from authsome.auth.sessions import AuthSession


@dataclass
class FlowResult:
    """Returned by every flow's authenticate() method.

    client_record is only populated by DCR-based flows that register a new
    OAuth client as part of the authentication process.
    """

    connection: ConnectionRecord
    client_record: ProviderClientRecord | None = None


class AuthFlow(ABC):
    """Abstract authentication flow handler.

    Flows return FlowResult with plaintext credential fields.
    Encryption is handled by the Vault when the record is persisted.
    """

    @abstractmethod
    async def begin(
        self,
        provider: ProviderDefinition,
        identity: str | None,
        connection_name: str,
        runtime_session: AuthSession,
        scopes: list[str] | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """Start the authentication flow.

        Must populate runtime_session.payload with flow-specific data
        and transition the session to 'waiting_for_user' or 'processing'.
        """
        ...

    @abstractmethod
    async def resume(
        self,
        provider: ProviderDefinition,
        identity: str | None,
        connection_name: str,
        runtime_session: AuthSession,
        callback_data: dict[str, Any],
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> FlowResult | None:
        """Resume the authentication flow with callback or input data.

        Returns the final FlowResult or None if the flow is still pending.
        """
        ...

    async def revoke(
        self,
        provider: ProviderDefinition,
        record: ConnectionRecord,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        """Revoke stored credentials on the remote server (RFC 7009).

        Attempts to revoke the access token first, then the refresh token.
        Supplied client credentials will be included in the payload if provided.
        All exceptions are swallowed and logged as warnings to avoid disrupting the logout flow.
        """
        revocation_url = provider.oauth.revocation_url if provider.oauth else None
        if not revocation_url:
            return

        def _do_revoke(token: str, token_type: str) -> None:
            payload = {"token": token}
            if client_id:
                payload["client_id"] = client_id
            if client_secret:
                payload["client_secret"] = client_secret

            try:
                http_client.post(
                    revocation_url,
                    data=payload,
                    timeout=15,
                )
            except Exception as exc:
                logger.warning(f"{token_type.capitalize()} token revocation failed (continuing): {{}}", exc)

        if record.access_token:
            _do_revoke(record.access_token, "access")

        if record.refresh_token:
            _do_revoke(record.refresh_token, "refresh")

    def refresh(
        self,
        provider: ProviderDefinition,
        record: ConnectionRecord,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> ConnectionRecord:
        """Refresh an OAuth2 token.

        Standard implementation covering RFC6749 token refresh grant.
        Subclasses may override if the flow demands custom request shaping
        or uses dynamic registration keys.
        """
        if provider.oauth is None:
            raise RefreshFailedError("No OAuth config", provider=provider.name)
        if record.refresh_token is None:
            raise RefreshFailedError("No refresh token available", provider=provider.name)
        if not client_id:
            raise RefreshFailedError("No client_id available for refresh", provider=provider.name)

        payload: dict[str, str] = {
            "grant_type": "refresh_token",
            "refresh_token": record.refresh_token,
            "client_id": client_id,
        }
        if client_secret:
            payload["client_secret"] = client_secret

        resp = http_client.post(
            provider.oauth.token_url,
            data=payload,
            headers={"Accept": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        token = resp.json()

        now = utc_now()
        record.access_token = token["access_token"]
        if "refresh_token" in token:
            record.refresh_token = token["refresh_token"]
        if "expires_in" in token:
            record.expires_at = now + timedelta(seconds=int(token["expires_in"]))
        record.obtained_at = now
        record.status = ConnectionStatus.CONNECTED

        return record
