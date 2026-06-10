"""Server-owned PoP replay caches."""

import time
from typing import Protocol

from authsome.identity.proof import ProofValidationError


class ReplayCache(Protocol):
    async def check_and_store(self, jti: str, exp: int) -> None:
        """Store a JTI until expiry or raise when it has already been used."""


class MemoryReplayCache:
    """Process-local replay cache for local development and tests."""

    def __init__(self) -> None:
        self._seen: dict[str, int] = {}

    async def check_and_store(self, jti: str, exp: int) -> None:
        now = int(time.time())
        self._seen = {key: value for key, value in self._seen.items() if value > now}
        if jti in self._seen:
            raise ProofValidationError("Proof JWT was already used")
        if exp > now:
            self._seen[jti] = exp


class RedisReplayCache:
    """Redis-backed replay cache shared across server replicas."""

    def __init__(self, client, *, key_prefix: str = "authsome:pop:jti") -> None:
        self._client = client
        self._key_prefix = key_prefix.rstrip(":")

    async def check_and_store(self, jti: str, exp: int) -> None:
        ttl = max(exp - int(time.time()), 1)
        key = f"{self._key_prefix}:{jti}"
        stored = await self._client.set(key, "1", ex=ttl, nx=True)
        if not stored:
            raise ProofValidationError("Proof JWT was already used")
