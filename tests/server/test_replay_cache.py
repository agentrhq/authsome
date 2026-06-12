import time

import pytest

from authsome.identity.proof import ProofValidationError
from authsome.server.replay_cache import MemoryReplayCache


@pytest.mark.asyncio
async def test_memory_replay_cache_rejects_duplicate_jti() -> None:
    cache = MemoryReplayCache()
    exp = int(time.time()) + 60

    await cache.check_and_store("jti-1", exp)

    with pytest.raises(ProofValidationError, match="already used"):
        await cache.check_and_store("jti-1", exp)


@pytest.mark.asyncio
async def test_memory_replay_cache_drops_expired_entries() -> None:
    cache = MemoryReplayCache()

    await cache.check_and_store("jti-1", int(time.time()) - 1)
    await cache.check_and_store("jti-1", int(time.time()) + 60)
