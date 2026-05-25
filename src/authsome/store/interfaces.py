"""Unified storage interfaces for Authsome."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from key_value.aio.protocols.key_value import AsyncKeyValue


# TODO: Name app store doesn't seem correct at all
class AppStore(ABC):
    """Storage backend for the encrypted vault KV."""

    @property
    @abstractmethod
    def home(self) -> Path:
        """Base directory for this storage system."""
        ...

    @property
    @abstractmethod
    def kv(self) -> AsyncKeyValue:
        """The underlying async key-value store."""
        ...

    # ── Initialization ────────────────────────────────────────────────────

    @abstractmethod
    async def ensure_initialized(self) -> None:
        """Seed the store with version marker and default config."""
        ...

    @abstractmethod
    async def is_healthy(self) -> bool:
        """Check if the store is accessible."""
        ...

    @abstractmethod
    async def check_integrity(self) -> bool:
        """Perform a health check on the storage medium."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close all underlying storage connections."""
        ...
