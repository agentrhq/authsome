"""Hosted browser sessions and pending identity-claim storage."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from pydantic import BaseModel, Field

from authsome.server.hosted_auth import UI_TOKEN_AUDIENCE
from authsome.utils import utc_now

DEFAULT_UI_BOOTSTRAP_TTL_SECONDS = 300
DEFAULT_UI_SESSION_TTL_SECONDS = 3600


class PendingClaimToken(BaseModel):
    """Short-lived token for an identity waiting to be claimed."""

    token: str
    identity: str
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime = Field(
        default_factory=lambda: utc_now() + timedelta(seconds=DEFAULT_UI_BOOTSTRAP_TTL_SECONDS)
    )

    @property
    def is_expired(self) -> bool:
        return utc_now() >= self.expires_at


class HostedBrowserSession(BaseModel):
    """Principal-scoped hosted browser session."""

    principal_id: str
    email: str
    token: str
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime

    @property
    def is_expired(self) -> bool:
        return utc_now() >= self.expires_at


class UiSessionStore:
    """In-memory hosted UI session helper with signed JWT cookies."""

    def __init__(self, signing_secret: str | bytes) -> None:
        self._secret = signing_secret.encode("utf-8") if isinstance(signing_secret, str) else signing_secret
        self._pending_claims: dict[str, PendingClaimToken] = {}

    def create_pending_claim(
        self,
        *,
        identity: str,
        ttl_seconds: int = DEFAULT_UI_BOOTSTRAP_TTL_SECONDS,
    ) -> PendingClaimToken:
        self.cleanup_expired()
        pending = PendingClaimToken(
            token=f"claim_{secrets.token_urlsafe(24)}",
            identity=identity,
            expires_at=utc_now() + timedelta(seconds=ttl_seconds),
        )
        self._pending_claims[pending.token] = pending
        return pending

    def get_pending_claim(self, token: str) -> PendingClaimToken:
        self.cleanup_expired()
        pending = self._pending_claims.get(token)
        if pending is None or pending.is_expired:
            self._pending_claims.pop(token, None)
            raise KeyError(f"Pending claim token not found: {token}")
        return pending

    def consume_pending_claim(self, token: str) -> PendingClaimToken:
        pending = self.get_pending_claim(token)
        self._pending_claims.pop(token, None)
        return pending

    def create_browser_session(
        self,
        *,
        principal_id: str,
        email: str,
        ttl_seconds: int = DEFAULT_UI_SESSION_TTL_SECONDS,
    ) -> HostedBrowserSession:
        issued_at = utc_now()
        expires_at = issued_at + timedelta(seconds=ttl_seconds)
        payload = {
            "sub": principal_id,
            "email": email,
            "aud": UI_TOKEN_AUDIENCE,
            "iat": int(issued_at.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        token = jwt.encode(payload, self._secret, algorithm="HS256")
        return HostedBrowserSession(
            principal_id=principal_id,
            email=email,
            token=token,
            created_at=issued_at,
            expires_at=expires_at,
        )

    def get_browser_session(self, cookie_value: str) -> HostedBrowserSession:
        token = self._verify_cookie(cookie_value)
        try:
            claims = jwt.decode(token, self._secret, algorithms=["HS256"], audience=UI_TOKEN_AUDIENCE)
        except jwt.PyJWTError as exc:
            raise KeyError("Invalid hosted browser session") from exc
        expires_at = datetime.fromtimestamp(int(claims["exp"]), tz=UTC)
        session = HostedBrowserSession(
            principal_id=str(claims["sub"]),
            email=str(claims["email"]),
            token=token,
            created_at=datetime.fromtimestamp(int(claims["iat"]), tz=UTC),
            expires_at=expires_at,
        )
        if session.is_expired:
            raise KeyError("Hosted browser session expired")
        return session

    def build_cookie_value(self, token: str) -> str:
        signature = hmac.new(self._secret, token.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{token}.{signature}"

    def delete_browser_session(self, cookie_value: str) -> None:
        self._verify_cookie(cookie_value)

    def cleanup_expired(self) -> None:
        expired_claims = [token for token, pending in self._pending_claims.items() if pending.is_expired]
        for token in expired_claims:
            self._pending_claims.pop(token, None)

    def _verify_cookie(self, cookie_value: str) -> str:
        token, sep, signature = cookie_value.rpartition(".")
        if not token or not sep or not signature:
            raise KeyError("Malformed UI session cookie")
        expected = self.build_cookie_value(token).rpartition(".")[2]
        if not hmac.compare_digest(signature, expected):
            raise KeyError("Invalid UI session cookie signature")
        return token
