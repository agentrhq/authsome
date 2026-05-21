from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from authsome.cli.daemon_control import DaemonHomeMismatchError, _assert_managed_daemon_home_matches


@pytest.mark.asyncio
async def test_managed_daemon_home_guard_allows_matching_home(tmp_path: Path) -> None:
    client = AsyncMock()
    client.base_url = "http://127.0.0.1:7998"
    client.health.return_value = {
        "status": "ok",
        "version": "0.0.0",
        "home": str(tmp_path),
    }

    await _assert_managed_daemon_home_matches(client, tmp_path)


@pytest.mark.asyncio
async def test_managed_daemon_home_guard_rejects_mismatched_home(tmp_path: Path) -> None:
    client = AsyncMock()
    client.base_url = "http://127.0.0.1:7998"
    client.health.return_value = {
        "status": "ok",
        "version": "0.0.0",
        "home": "/Users/ankitranjan/.authsome",
    }

    with pytest.raises(DaemonHomeMismatchError, match="AUTHSOME_HOME"):
        await _assert_managed_daemon_home_matches(client, tmp_path)
