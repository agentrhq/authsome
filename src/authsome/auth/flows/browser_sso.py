"""Browser SSO authentication flow.

begin() — populates session payload for the CLI to launch CloakBrowser.
resume() — stores extracted credentials returned by the CLI into a ConnectionRecord.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from authsome.auth.flows.base import AuthFlow, FlowResult
from authsome.auth.models.connection import AccountInfo, ConnectionRecord
from authsome.auth.models.enums import AuthType, ConnectionStatus
from authsome.auth.models.provider import ProviderDefinition
from authsome.errors import AuthenticationFailedError, RefreshFailedError
from authsome.utils import utc_now

if TYPE_CHECKING:
    from authsome.auth.sessions import AuthSession

_TTL_PATTERN = re.compile(r"^(\d+)(d|h|m)$")


def _parse_ttl_duration(ttl: str | None) -> timedelta | None:
    """Parse a TTL string like '30d', '24h', '90m' into a timedelta.

    Returns None for None input or unrecognised formats.
    """
    if ttl is None:
        return None
    m = _TTL_PATTERN.match(ttl.strip())
    if not m:
        return None
    value, unit = int(m.group(1)), m.group(2)
    if unit == "d":
        return timedelta(days=value)
    if unit == "h":
        return timedelta(hours=value)
    return timedelta(minutes=value)


class BrowserSSOFlow(AuthFlow):
    """Browser SSO flow — cookie extraction via CloakBrowser on the CLI side."""

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
        if provider.browser_sso is None:
            raise AuthenticationFailedError(
                "Provider missing 'browser_sso' configuration",
                provider=provider.name,
            )
        cfg = provider.browser_sso
        runtime_session.state = "waiting_for_user"
        runtime_session.payload["entry_url"] = cfg.entry_url
        runtime_session.payload["domains"] = cfg.domains
        runtime_session.payload["validate_url"] = cfg.validate_url
        runtime_session.payload["extract"] = [rule.model_dump(by_alias=True) for rule in cfg.extract]
        runtime_session.payload["extra_headers"] = cfg.extra_headers
        runtime_session.payload["network_proxy"] = cfg.network_proxy
        runtime_session.payload["login_mode"] = cfg.login_mode
        runtime_session.payload["ttl_from_cookie"] = cfg.ttl_from_cookie
        runtime_session.payload["browser_exec"] = cfg.browser_exec
        runtime_session.payload["browser_data_dir"] = cfg.browser_data_dir

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
        credentials = callback_data.get("credentials")
        if not credentials or not isinstance(credentials, dict):
            raise AuthenticationFailedError(
                "Browser SSO resume requires 'credentials' dict in callback_data",
                provider=provider.name,
            )

        now = utc_now()

        # Prefer the real server-set cookie expiry over the guessed ttl.
        # The CLI embeds it as a Unix timestamp string under "__cookie_expires_at__".
        expires_at = None
        raw_cookie_expiry = credentials.pop("__cookie_expires_at__", None)
        if raw_cookie_expiry:
            try:
                expires_at = datetime.fromtimestamp(int(raw_cookie_expiry), tz=UTC)
            except (ValueError, OSError):
                pass

        if not identity:
            raise AuthenticationFailedError(
                "Browser SSO resume requires an identity",
                provider=provider.name,
            )

        if expires_at is None:
            ttl_delta = _parse_ttl_duration(provider.browser_sso.ttl if provider.browser_sso else None)
            expires_at = now + ttl_delta if ttl_delta is not None else None

        return FlowResult(
            connection=ConnectionRecord(
                schema_version=2,
                provider=provider.name,
                identity=identity,
                connection_name=connection_name,
                auth_type=AuthType.BROWSER_SSO,
                status=ConnectionStatus.CONNECTED,
                credentials=credentials,
                expires_at=expires_at,
                obtained_at=now,
                account=AccountInfo(),
            )
        )

    def refresh(
        self,
        provider: ProviderDefinition,
        record: ConnectionRecord,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> ConnectionRecord:
        """Browser SSO has no token refresh — re-login is always required."""
        raise RefreshFailedError(
            "Browser SSO credentials cannot be refreshed automatically. Run: authsome login " + record.provider,
            provider=provider.name,
        )
