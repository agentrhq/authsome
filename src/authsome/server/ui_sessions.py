"""Hosted UI bootstrap and browser session storage."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from authsome.utils import utc_now

DEFAULT_UI_BOOTSTRAP_TTL_SECONDS = 300
DEFAULT_UI_SESSION_TTL_SECONDS = 3600


class UiBootstrapToken(BaseModel):
    """Single-use browser bootstrap token bound to a principal session."""

    token: str
    identity: str
    principal_id: str
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime = Field(
        default_factory=lambda: utc_now() + timedelta(seconds=DEFAULT_UI_BOOTSTRAP_TTL_SECONDS)
    )

    @property
    def is_expired(self) -> bool:
        return utc_now() >= self.expires_at


class UiClaimBootstrapToken(BaseModel):
    """Single-use browser bootstrap token for claim completion."""

    token: str
    identity: str
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime = Field(
        default_factory=lambda: utc_now() + timedelta(seconds=DEFAULT_UI_BOOTSTRAP_TTL_SECONDS)
    )

    @property
    def is_expired(self) -> bool:
        return utc_now() >= self.expires_at


class UiBrowserSession(BaseModel):
    """Short-lived hosted dashboard browser session."""

    session_id: str
    identity: str
    principal_id: str
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime = Field(default_factory=lambda: utc_now() + timedelta(seconds=DEFAULT_UI_SESSION_TTL_SECONDS))

    @property
    def is_expired(self) -> bool:
        return utc_now() >= self.expires_at


class UiSessionStore:
    """In-memory hosted UI session store with signed session cookies."""

    def __init__(self, signing_secret: str | bytes) -> None:
        self._secret = signing_secret.encode("utf-8") if isinstance(signing_secret, str) else signing_secret
        self._bootstraps: dict[str, UiBootstrapToken] = {}
        self._claim_bootstraps: dict[str, UiClaimBootstrapToken] = {}
        self._sessions: dict[str, UiBrowserSession] = {}

    def create_bootstrap(
        self,
        *,
        identity: str,
        principal_id: str,
        ttl_seconds: int = DEFAULT_UI_BOOTSTRAP_TTL_SECONDS,
    ) -> UiBootstrapToken:
        self.cleanup_expired()
        bootstrap = UiBootstrapToken(
            token=f"boot_{secrets.token_urlsafe(24)}",
            identity=identity,
            principal_id=principal_id,
            expires_at=utc_now() + timedelta(seconds=ttl_seconds),
        )
        self._bootstraps[bootstrap.token] = bootstrap
        return bootstrap

    def create_claim_bootstrap(
        self,
        *,
        identity: str,
        ttl_seconds: int = DEFAULT_UI_BOOTSTRAP_TTL_SECONDS,
    ) -> UiClaimBootstrapToken:
        self.cleanup_expired()
        bootstrap = UiClaimBootstrapToken(
            token=f"claim_{secrets.token_urlsafe(24)}",
            identity=identity,
            expires_at=utc_now() + timedelta(seconds=ttl_seconds),
        )
        self._claim_bootstraps[bootstrap.token] = bootstrap
        return bootstrap

    def consume_claim_bootstrap(self, token: str) -> UiClaimBootstrapToken:
        self.cleanup_expired()
        bootstrap = self._claim_bootstraps.pop(token, None)
        if bootstrap is None or bootstrap.is_expired:
            raise KeyError(f"UI claim bootstrap token not found: {token}")
        return bootstrap

    def consume_bootstrap(
        self,
        token: str,
        *,
        session_ttl_seconds: int = DEFAULT_UI_SESSION_TTL_SECONDS,
    ) -> UiBrowserSession:
        self.cleanup_expired()
        bootstrap = self._bootstraps.pop(token, None)
        if bootstrap is None or bootstrap.is_expired:
            raise KeyError(f"UI bootstrap token not found: {token}")
        return self.create_session(
            identity=bootstrap.identity,
            principal_id=bootstrap.principal_id,
            ttl_seconds=session_ttl_seconds,
        )

    def create_session(
        self,
        *,
        identity: str,
        principal_id: str,
        ttl_seconds: int = DEFAULT_UI_SESSION_TTL_SECONDS,
    ) -> UiBrowserSession:
        self.cleanup_expired()
        session = UiBrowserSession(
            session_id=f"uis_{secrets.token_urlsafe(18)}",
            identity=identity,
            principal_id=principal_id,
            expires_at=utc_now() + timedelta(seconds=ttl_seconds),
        )
        self._sessions[session.session_id] = session
        return session

    def get_session(self, cookie_value: str) -> UiBrowserSession:
        self.cleanup_expired()
        session_id = self._verify_cookie(cookie_value)
        session = self._sessions.get(session_id)
        if session is None or session.is_expired:
            self.delete_session(session_id)
            raise KeyError(f"UI session not found: {session_id}")
        return session

    def delete_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def build_cookie_value(self, session_id: str) -> str:
        signature = hmac.new(self._secret, session_id.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{session_id}.{signature}"

    def cleanup_expired(self) -> None:
        expired_bootstraps = [token for token, bootstrap in self._bootstraps.items() if bootstrap.is_expired]
        for token in expired_bootstraps:
            self._bootstraps.pop(token, None)

        expired_claim_bootstraps = [
            token for token, bootstrap in self._claim_bootstraps.items() if bootstrap.is_expired
        ]
        for token in expired_claim_bootstraps:
            self._claim_bootstraps.pop(token, None)

        expired_sessions = [session_id for session_id, session in self._sessions.items() if session.is_expired]
        for session_id in expired_sessions:
            self._sessions.pop(session_id, None)

    def _verify_cookie(self, cookie_value: str) -> str:
        session_id, sep, signature = cookie_value.partition(".")
        if not session_id or not sep or not signature:
            raise KeyError("Malformed UI session cookie")
        expected = self.build_cookie_value(session_id).partition(".")[2]
        if not hmac.compare_digest(signature, expected):
            raise KeyError("Invalid UI session cookie signature")
        return session_id
