"""Browser sessions and pending identity-claim storage."""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import jwt
from pydantic import BaseModel, Field

from authsome.server.config import get_server_config
from authsome.utils import utc_now

UI_TOKEN_AUDIENCE = "authsome-ui"

# Settings-backed session lifetimes (seconds).
DEFAULT_UI_BOOTSTRAP_TTL_SECONDS = get_server_config().ui_bootstrap_ttl_seconds
DEFAULT_UI_SESSION_TTL_SECONDS = get_server_config().ui_session_ttl_seconds


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


class PendingClaimStore(Protocol):
    """Async storage for short-lived identity claim tokens."""

    async def create(
        self,
        *,
        identity: str,
        ttl_seconds: int = DEFAULT_UI_BOOTSTRAP_TTL_SECONDS,
    ) -> PendingClaimToken:
        """Create a claim token for an identity."""

    async def get(self, token: str) -> PendingClaimToken:
        """Return a claim token by value."""

    async def consume(self, token: str) -> PendingClaimToken:
        """Return and remove a claim token by value."""


class BrowserSession(BaseModel):
    """Principal-scoped browser session."""

    principal_id: str
    email: str
    token: str
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime

    @property
    def is_expired(self) -> bool:
        return utc_now() >= self.expires_at


class MemoryPendingClaimStore:
    """In-memory pending claim token store."""

    def __init__(self) -> None:
        self._pending_claims: dict[str, PendingClaimToken] = {}

    async def create(
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

    async def get(self, token: str) -> PendingClaimToken:
        self.cleanup_expired()
        pending = self._pending_claims.get(token)
        if pending is None or pending.is_expired:
            self._pending_claims.pop(token, None)
            raise KeyError(f"Pending claim token not found: {token}")
        return pending

    async def consume(self, token: str) -> PendingClaimToken:
        pending = await self.get(token)
        self._pending_claims.pop(token, None)
        return pending

    def cleanup_expired(self) -> None:
        expired_claims = [token for token, pending in self._pending_claims.items() if pending.is_expired]
        for token in expired_claims:
            self._pending_claims.pop(token, None)


class RedisPendingClaimStore:
    """Redis-backed pending claim token store shared across server replicas."""

    def __init__(self, client: Any, *, key_prefix: str = "authsome:ui-session") -> None:
        self._client = client
        self._key_prefix = key_prefix.rstrip(":")

    def _pending_claim_key(self, token: str) -> str:
        return f"{self._key_prefix}:pending-claim:{token}"

    async def create(
        self,
        *,
        identity: str,
        ttl_seconds: int = DEFAULT_UI_BOOTSTRAP_TTL_SECONDS,
    ) -> PendingClaimToken:
        pending = PendingClaimToken(
            token=f"claim_{secrets.token_urlsafe(24)}",
            identity=identity,
            expires_at=utc_now() + timedelta(seconds=ttl_seconds),
        )
        await self._client.set(
            self._pending_claim_key(pending.token),
            pending.model_dump_json(),
            ex=max(int(ttl_seconds), 1),
        )
        return pending

    async def get(self, token: str) -> PendingClaimToken:
        raw = await self._client.get(self._pending_claim_key(token))
        if raw is None:
            raise KeyError(f"Pending claim token not found: {token}")
        if isinstance(raw, bytes):
            raw = raw.decode()
        pending = PendingClaimToken.model_validate_json(raw)
        if pending.is_expired:
            await self._client.delete(self._pending_claim_key(token))
            raise KeyError(f"Pending claim token not found: {token}")
        return pending

    async def consume(self, token: str) -> PendingClaimToken:
        pending = await self.get(token)
        await self._client.delete(self._pending_claim_key(token))
        return pending


class UiSessionStore:
    """In-memory UI session helper with signed JWT cookies."""

    def __init__(
        self,
        signing_secret: str | bytes,
        pending_claims: PendingClaimStore | None = None,
    ) -> None:
        self._secret = signing_secret.encode("utf-8") if isinstance(signing_secret, str) else signing_secret
        self._pending_claim_store = pending_claims or MemoryPendingClaimStore()

    async def create_pending_claim(
        self,
        *,
        identity: str,
        ttl_seconds: int = DEFAULT_UI_BOOTSTRAP_TTL_SECONDS,
    ) -> PendingClaimToken:
        return await self._pending_claim_store.create(identity=identity, ttl_seconds=ttl_seconds)

    async def get_pending_claim(self, token: str) -> PendingClaimToken:
        return await self._pending_claim_store.get(token)

    async def consume_pending_claim(self, token: str) -> PendingClaimToken:
        return await self._pending_claim_store.consume(token)

    def create_browser_session(
        self,
        *,
        principal_id: str,
        email: str,
        ttl_seconds: int = DEFAULT_UI_SESSION_TTL_SECONDS,
    ) -> BrowserSession:
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
        return BrowserSession(
            principal_id=principal_id,
            email=email,
            token=token,
            created_at=issued_at,
            expires_at=expires_at,
        )

    def get_browser_session(self, cookie_value: str) -> BrowserSession:
        token = self._verify_cookie(cookie_value)
        try:
            claims = jwt.decode(token, self._secret, algorithms=["HS256"], audience=UI_TOKEN_AUDIENCE)
        except jwt.PyJWTError as exc:
            raise KeyError("Invalid browser session") from exc
        expires_at = datetime.fromtimestamp(int(claims["exp"]), tz=UTC)
        session = BrowserSession(
            principal_id=str(claims["sub"]),
            email=str(claims["email"]),
            token=token,
            created_at=datetime.fromtimestamp(int(claims["iat"]), tz=UTC),
            expires_at=expires_at,
        )
        if session.is_expired:
            raise KeyError("Browser session expired")
        return session

    def build_cookie_value(self, token: str) -> str:
        signature = hmac.new(self._secret, token.encode("utf-8"), hashlib.sha256).hexdigest()
        return f"{token}.{signature}"

    def delete_browser_session(self, cookie_value: str) -> None:
        self._verify_cookie(cookie_value)

    def _verify_cookie(self, cookie_value: str) -> str:
        token, sep, signature = cookie_value.rpartition(".")
        if not token or not sep or not signature:
            raise KeyError("Malformed UI session cookie")
        expected = self.build_cookie_value(token).rpartition(".")[2]
        if not hmac.compare_digest(signature, expected):
            raise KeyError("Invalid UI session cookie signature")
        return token
