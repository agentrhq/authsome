"""Browser session cookie authentication flow.

begin()  — daemon-side: stash config in session payload.
resume() — daemon-side: build ConnectionRecord from CLI-supplied cookies.
run_login() — CLI-side: read Chrome cookie DB, open browser if needed, poll until valid.
"""

from __future__ import annotations

import asyncio
import webbrowser
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

from loguru import logger

from authsome.auth.browser_cookies import (
    COOKIE_EXPIRES_AT_KEY,
    cookies_are_valid,
    normalize_jsessionid,
    read_chrome_cookies,
)
from authsome.auth.flows.base import AuthFlow, FlowResult
from authsome.auth.models.connection import AccountInfo, ConnectionRecord
from authsome.auth.models.enums import AuthType, ConnectionStatus
from authsome.auth.models.provider import ProviderDefinition
from authsome.errors import AuthenticationFailedError, RefreshFailedError
from authsome.utils import utc_now

if TYPE_CHECKING:
    from authsome.auth.sessions import AuthSession

_POLL_INTERVAL = 4.0
_DEFAULT_TIMEOUT = 300.0


class BrowserFlow(AuthFlow):
    """Cookie-based browser SSO — reads Chrome's on-disk cookie database."""

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
        if provider.browser is None:
            raise AuthenticationFailedError("Provider missing 'browser' configuration", provider=provider.name)
        cfg = provider.browser
        runtime_session.state = "waiting_for_user"
        runtime_session.payload["browser_login"] = True
        runtime_session.payload["entry_url"] = cfg.entry_url
        runtime_session.payload["domains"] = cfg.domains
        runtime_session.payload["auth_cookies"] = cfg.auth_cookies
        runtime_session.payload["ttl_from_cookie"] = cfg.ttl_from_cookie
        runtime_session.payload["ttl_hours"] = cfg.ttl_hours

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
        if provider.browser is None:
            raise AuthenticationFailedError("Provider missing 'browser' configuration", provider=provider.name)
        credentials = callback_data.get("credentials")
        if not credentials or not isinstance(credentials, dict):
            return None

        now = utc_now()
        stored_credentials = dict(credentials)
        expires_at = _resolve_browser_expires_at(
            stored_credentials,
            ttl_hours=provider.browser.ttl_hours,
            now=now,
        )
        return FlowResult(
            connection=ConnectionRecord(
                schema_version=2,
                provider=provider.name,
                identity=identity,
                connection_name=connection_name,
                auth_type=AuthType.BROWSER,
                status=ConnectionStatus.CONNECTED,
                credentials=stored_credentials,
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
        raise RefreshFailedError(
            f"Browser cookies cannot be refreshed automatically — run: authsome login {record.provider}",
            provider=record.provider,
        )

    @staticmethod
    async def run_login(
        action: dict[str, Any],
        provider_name: str,
        *,
        poll_interval: float = _POLL_INTERVAL,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> dict[str, str]:
        """CLI-side login: read Chrome cookies, open browser if needed, poll until valid.

        Args:
            action: The ``BrowserAction`` payload from ``next_action``.
            provider_name: Provider name, used to select normalization (e.g. LinkedIn).
            poll_interval: Seconds between cookie DB reads.
            timeout: Total seconds before ``TimeoutError`` is raised.

        Returns:
            Cookie name→value dict ready to POST to ``/auth/sessions/{id}/resume``.
        """
        entry_url: str = action["entry_url"]
        domains: list[str] = action.get("domains", [])
        auth_cookies: list[str] = action.get("auth_cookies", [])
        ttl_from_cookie: str | None = action.get("ttl_from_cookie")

        def _read() -> dict[str, str] | None:
            try:
                cookies = read_chrome_cookies(domains, ttl_from_cookie=ttl_from_cookie)
                if provider_name == "linkedin-browser":
                    cookies = normalize_jsessionid(cookies)
                if cookies_are_valid(cookies, auth_cookies):
                    return cookies
            except Exception as exc:
                logger.debug("Cookie read failed: {}", exc)
            return None

        # Fast path: already logged in
        if result := _read():
            logger.debug("authsome: existing cookies valid for {} — no browser open needed", provider_name)
            return result

        # Open browser for user to log in
        try:
            webbrowser.open(entry_url)
        except Exception as exc:
            logger.warning("Could not open browser: {}", exc)

        deadline = asyncio.get_event_loop().time() + timeout
        while True:
            await asyncio.sleep(poll_interval)
            if result := _read():
                logger.info("authsome: browser cookies captured for {}", provider_name)
                return result
            if asyncio.get_event_loop().time() >= deadline:
                raise TimeoutError(
                    f"Timed out waiting for browser login to {entry_url!r} after {int(timeout)}s. "
                    "Please complete login in the browser window."
                )


def _resolve_browser_expires_at(
    credentials: dict[str, str],
    *,
    ttl_hours: int,
    now: datetime,
) -> datetime:
    """Use real cookie expiry when present, otherwise fall back to ttl_hours."""
    raw_expiry = credentials.pop(COOKIE_EXPIRES_AT_KEY, None)
    if raw_expiry:
        try:
            return datetime.fromtimestamp(int(raw_expiry), tz=UTC)
        except (ValueError, OSError):
            pass
    return now + timedelta(hours=ttl_hours)
