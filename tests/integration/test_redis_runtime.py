import os
import time
import uuid

import pytest

from authsome.auth.models.enums import FlowType
from authsome.identity.proof import ProofValidationError
from authsome.server.auth_sessions import RedisAuthSessionStore
from authsome.server.replay_cache import RedisReplayCache
from authsome.server.ui_sessions import RedisPendingClaimStore

pytestmark = pytest.mark.asyncio


def _redis_url() -> str:
    value = os.environ.get("AUTHSOME_TEST_REDIS_URL")
    if not value:
        pytest.skip("AUTHSOME_TEST_REDIS_URL is not set")
    return value


async def _client():
    pytest.importorskip("redis.asyncio")
    from redis.asyncio import Redis

    client = Redis.from_url(_redis_url(), decode_responses=True)
    await client.ping()
    return client


@pytest.mark.asyncio
async def test_redis_replay_cache_rejects_duplicate() -> None:
    client = await _client()
    prefix = f"test:authsome:{uuid.uuid4().hex}:jti"
    cache = RedisReplayCache(client, key_prefix=prefix)
    try:
        await cache.check_and_store("jti-1", int(time.time()) + 60)
        with pytest.raises(ProofValidationError, match="already used"):
            await cache.check_and_store("jti-1", int(time.time()) + 60)
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_redis_auth_session_store_survives_new_store_instance() -> None:
    client = await _client()
    prefix = f"test:authsome:{uuid.uuid4().hex}:session"
    first = RedisAuthSessionStore(client, key_prefix=prefix)
    second = RedisAuthSessionStore(client, key_prefix=prefix)
    try:
        session = await first.create(
            provider="github",
            identity="agent-1",
            principal_id="principal_1",
            connection_name="default",
            flow_type=FlowType.PKCE.value,
        )
        session.payload["internal_state"] = "state-1"
        await first.index_oauth_state(session)

        assert (await second.get(session.session_id)).identity == "agent-1"
        assert (await second.get_by_oauth_state("state-1")).session_id == session.session_id
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_redis_pending_claim_store_consumes_once() -> None:
    client = await _client()
    prefix = f"test:authsome:{uuid.uuid4().hex}:claim"
    store = RedisPendingClaimStore(client, key_prefix=prefix)
    try:
        pending = await store.create(identity="agent-1")

        assert (await store.consume(pending.token)).identity == "agent-1"
        with pytest.raises(KeyError):
            await store.consume(pending.token)
    finally:
        await client.aclose()
