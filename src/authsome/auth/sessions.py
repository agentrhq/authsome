"""Auth-owned session models and in-memory session store."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from authsome.utils import utc_now

DEFAULT_SESSION_TTL_SECONDS = 300


class AuthSessionStatus(StrEnum):
    PENDING = "pending"
    WAITING_FOR_USER = "waiting_for_user"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class AuthSession(BaseModel):
    """Internal auth session state.

    This intentionally mirrors the fields existing flow handlers need today
    while moving ownership into the auth package.
    """

    session_id: str
    provider: str
    identity: str
    principal_id: str | None = None
    connection_name: str
    flow_type: str
    state: str = AuthSessionStatus.PENDING
    status_message: str | None = None
    error_message: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime = Field(default_factory=lambda: utc_now() + timedelta(seconds=DEFAULT_SESSION_TTL_SECONDS))

    @property
    def is_expired(self) -> bool:
        return utc_now() >= self.expires_at


class AuthSessionStore:
    """In-memory auth session state for the daemon process."""

    def __init__(self) -> None:
        self._sessions: dict[str, AuthSession] = {}
        self._state_index: dict[str, str] = {}

    async def create(
        self,
        *,
        provider: str,
        identity: str,
        principal_id: str | None,
        connection_name: str,
        flow_type: str,
        ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
    ) -> AuthSession:
        self.cleanup_expired()
        session = AuthSession(
            session_id=f"sess_{uuid.uuid4().hex[:12]}",
            provider=provider,
            identity=identity,
            principal_id=principal_id,
            connection_name=connection_name,
            flow_type=flow_type,
            expires_at=utc_now() + timedelta(seconds=ttl_seconds),
        )
        self._sessions[session.session_id] = session
        return session

    async def get(self, session_id: str) -> AuthSession:
        self.cleanup_expired()
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(f"Session not found: {session_id}")
        if session.is_expired:
            session.state = AuthSessionStatus.EXPIRED
            await self.delete(session_id)
            raise KeyError(f"Session expired: {session_id}")
        return session

    async def save(self, session: AuthSession) -> None:
        session.updated_at = utc_now()
        self._sessions[session.session_id] = session
        oauth_state = session.payload.get("internal_state")
        if oauth_state:
            self._state_index[str(oauth_state)] = session.session_id

    async def delete(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session:
            oauth_state = session.payload.get("internal_state")
            if oauth_state:
                self._state_index.pop(str(oauth_state), None)

    async def index_oauth_state(self, session: AuthSession) -> None:
        oauth_state = session.payload.get("internal_state")
        if oauth_state:
            self._state_index[str(oauth_state)] = session.session_id
        await self.save(session)

    async def get_by_oauth_state(self, state: str) -> AuthSession:
        self.cleanup_expired()
        session_id = self._state_index.get(state)
        if session_id is None:
            raise KeyError(f"Session not found for OAuth state: {state}")
        return await self.get(session_id)

    def cleanup_expired(self) -> None:
        expired = [session_id for session_id, session in self._sessions.items() if session.is_expired]
        for session_id in expired:
            session = self._sessions.get(session_id)
            if session is not None:
                session.state = AuthSessionStatus.EXPIRED
            self._sessions.pop(session_id, None)
            if session is not None:
                oauth_state = session.payload.get("internal_state")
                if oauth_state:
                    self._state_index.pop(str(oauth_state), None)
