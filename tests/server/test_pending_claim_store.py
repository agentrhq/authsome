import pytest

from authsome.server.ui_sessions import MemoryPendingClaimStore, RedisPendingClaimStore, UiSessionStore


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
async def test_memory_pending_claim_store_create_get_consume() -> None:
    store = MemoryPendingClaimStore()

    pending = await store.create(identity="agent-1")

    assert (await store.get(pending.token)).identity == "agent-1"
    assert (await store.consume(pending.token)).identity == "agent-1"
    with pytest.raises(KeyError):
        await store.get(pending.token)


def test_ui_session_store_keeps_browser_sessions_stateless() -> None:
    ui_sessions = UiSessionStore("test-secret")

    session = ui_sessions.create_browser_session(principal_id="principal_1", email="dev@example.com")
    cookie = ui_sessions.build_cookie_value(session.token)

    assert ui_sessions.get_browser_session(cookie).principal_id == "principal_1"


@pytest.mark.asyncio
async def test_redis_pending_claim_store_consumes_once() -> None:
    client = FakeRedisClient()
    store = RedisPendingClaimStore(client)

    pending = await store.create(identity="agent-1")

    assert (await store.get(pending.token)).identity == "agent-1"
    assert (await store.consume(pending.token)).identity == "agent-1"
    with pytest.raises(KeyError):
        await store.get(pending.token)
