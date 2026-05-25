"""Local disk-backed implementation of the AppStore."""

from __future__ import annotations

from pathlib import Path

from key_value.aio.protocols.key_value import AsyncKeyValue
from key_value.aio.stores.disk import DiskStore

from authsome.paths import get_server_home
from authsome.store.interfaces import AppStore

_CONFIG_COLLECTION = "config"


class LocalAppStore(AppStore):
    """Disk-backed AppStore for the daemon vault KV."""

    def __init__(self, home_dir: Path) -> None:
        self._home = home_dir
        self._home.mkdir(parents=True, exist_ok=True)
        self._server_home = get_server_home(home_dir)
        self._server_home.mkdir(parents=True, exist_ok=True)
        self._store = DiskStore(directory=str(self._server_home / "kv_store"))

    @property
    def home(self) -> Path:
        return self._home

    @property
    def server_home(self) -> Path:
        return self._server_home

    @property
    def kv(self) -> AsyncKeyValue:
        return self._store

    # ── Initialization ────────────────────────────────────────────────────

    async def ensure_initialized(self) -> None:
        if await self._store.get("version", collection=_CONFIG_COLLECTION) is not None:
            return
        await self._store.put("version", {"data": "1"}, collection=_CONFIG_COLLECTION)

    async def is_healthy(self) -> bool:
        return True

    async def check_integrity(self) -> bool:
        return True

    async def close(self) -> None:
        close = getattr(self._store, "close", None)
        if callable(close):
            await self._store.close()
