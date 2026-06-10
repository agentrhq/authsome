import pytest

from authsome.auth.models.enums import FlowType
from authsome.server.auth_sessions import RedisAuthSessionStore


class FakeRedisClient:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}
        self.ttls: dict[str, int | None] = {}

    async def get(self, key: str):
        return self.data.get(key)

    async def set(self, key: str, value: str, *, ex: int | None = None, nx: bool | None = None):
        if nx and key in self.data:
            return False
        self.data[key] = value
        self.ttls[key] = ex
        return True

    async def delete(self, *keys: str):
        deleted = 0
        for key in keys:
            if key in self.data:
                deleted += 1
            self.data.pop(key, None)
            self.ttls.pop(key, None)
        return deleted


@pytest.mark.asyncio
async def test_redis_session_store_round_trips_session_json() -> None:
    client = FakeRedisClient()
    store = RedisAuthSessionStore(client)

    session = await store.create(
        provider="github",
        identity="agent-1",
        principal_id="principal_1",
        connection_name="default",
        flow_type=FlowType.PKCE.value,
    )
    session.payload["internal_state"] = "state-123"
    session.status_message = "waiting"

    await store.save(session)

    loaded = await store.get(session.session_id)
    assert loaded.session_id == session.session_id
    assert loaded.payload["internal_state"] == "state-123"
    assert loaded.status_message == "waiting"


@pytest.mark.asyncio
async def test_redis_session_store_indexes_oauth_state() -> None:
    client = FakeRedisClient()
    store = RedisAuthSessionStore(client)
    session = await store.create(
        provider="github",
        identity="agent-1",
        principal_id="principal_1",
        connection_name="default",
        flow_type=FlowType.PKCE.value,
    )
    session.payload["internal_state"] = "state-123"

    await store.index_oauth_state(session)

    assert (await store.get_by_oauth_state("state-123")).session_id == session.session_id


@pytest.mark.asyncio
async def test_redis_session_store_delete_clears_session_and_state_indexes() -> None:
    client = FakeRedisClient()
    store = RedisAuthSessionStore(client)
    session = await store.create(
        provider="github",
        identity="agent-1",
        principal_id="principal_1",
        connection_name="default",
        flow_type=FlowType.PKCE.value,
    )
    session.payload["internal_state"] = "state-123"
    await store.save(session)

    await store.delete(session.session_id)

    assert await client.get(f"authsome:auth-session:session:{session.session_id}") is None
    assert await client.get("authsome:auth-session:oauth-state:state-123") is None
    assert await client.get(f"authsome:auth-session:session-state:{session.session_id}") is None


@pytest.mark.asyncio
async def test_redis_session_store_delete_uses_reverse_state_mapping_when_session_missing() -> None:
    client = FakeRedisClient()
    store = RedisAuthSessionStore(client)
    session = await store.create(
        provider="github",
        identity="agent-1",
        principal_id="principal_1",
        connection_name="default",
        flow_type=FlowType.PKCE.value,
    )
    session.payload["internal_state"] = "state-123"
    await store.save(session)

    client.data.pop(f"authsome:auth-session:session:{session.session_id}")

    await store.delete(session.session_id)

    assert await client.get(f"authsome:auth-session:session:{session.session_id}") is None
    assert await client.get("authsome:auth-session:oauth-state:state-123") is None
    assert await client.get(f"authsome:auth-session:session-state:{session.session_id}") is None
