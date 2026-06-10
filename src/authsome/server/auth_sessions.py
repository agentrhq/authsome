"""Server-owned Redis auth session storage."""

import uuid
from datetime import timedelta
from typing import Any

from authsome.auth.sessions import DEFAULT_SESSION_TTL_SECONDS, AuthSession
from authsome.utils import utc_now


class RedisAuthSessionStore:
    """Redis-backed auth session store shared across server replicas."""

    def __init__(self, client: Any, *, key_prefix: str = "authsome:auth-session") -> None:
        self._client = client
        self._key_prefix = key_prefix.rstrip(":")

    def _session_key(self, session_id: str) -> str:
        return f"{self._key_prefix}:session:{session_id}"

    def _state_key(self, state: str) -> str:
        return f"{self._key_prefix}:oauth-state:{state}"

    def _session_state_key(self, session_id: str) -> str:
        return f"{self._key_prefix}:session-state:{session_id}"

    async def create(  # noqa: PLR0913
        self,
        *,
        provider: str,
        identity: str | None,
        principal_id: str | None,
        connection_name: str,
        flow_type: str,
        ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
    ) -> AuthSession:
        session = AuthSession(
            session_id=f"sess_{uuid.uuid4().hex[:12]}",
            provider=provider,
            identity=identity,
            principal_id=principal_id,
            connection_name=connection_name,
            flow_type=flow_type,
            expires_at=utc_now() + timedelta(seconds=ttl_seconds),
        )
        await self.save(session)
        return session

    async def get(self, session_id: str) -> AuthSession:
        raw = await self._client.get(self._session_key(session_id))
        if raw is None:
            raise KeyError(f"Session not found: {session_id}")
        session = AuthSession.model_validate_json(raw)
        if session.is_expired:
            await self.delete(session_id)
            raise KeyError(f"Session expired: {session_id}")
        return session

    async def save(self, session: AuthSession) -> None:
        session.updated_at = utc_now()
        ttl = max(int((session.expires_at - utc_now()).total_seconds()), 1)
        await self._client.set(self._session_key(session.session_id), session.model_dump_json(), ex=ttl)
        oauth_state = session.payload.get("internal_state")
        if oauth_state:
            state = str(oauth_state)
            await self._client.set(self._state_key(state), session.session_id, ex=ttl)
            await self._client.set(self._session_state_key(session.session_id), state, ex=ttl)

    async def delete(self, session_id: str) -> None:
        raw = await self._client.get(self._session_key(session_id))
        if raw is None:
            state = await self._client.get(self._session_state_key(session_id))
            keys = [self._session_key(session_id), self._session_state_key(session_id)]
            if state is not None:
                if isinstance(state, bytes):
                    state = state.decode()
                keys.append(self._state_key(str(state)))
            await self._client.delete(*keys)
            return

        session = AuthSession.model_validate_json(raw)
        keys = [self._session_key(session_id)]
        oauth_state = session.payload.get("internal_state")
        if oauth_state:
            state = str(oauth_state)
            keys.extend([self._state_key(state), self._session_state_key(session_id)])
        await self._client.delete(*keys)

    async def index_oauth_state(self, session: AuthSession) -> None:
        await self.save(session)

    async def get_by_oauth_state(self, state: str) -> AuthSession:
        session_id = await self._client.get(self._state_key(state))
        if session_id is None:
            raise KeyError(f"Session not found for OAuth state: {state}")
        if isinstance(session_id, bytes):
            session_id = session_id.decode()
        return await self.get(str(session_id))
