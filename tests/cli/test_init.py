"""Tests for `authsome init`."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import MagicMock

from click.testing import CliRunner

from authsome.cli.main import cli
from authsome.identity import mark_registered, save_client_config
from authsome.identity.client_config import ClientConfig, load_client_config
from authsome.identity.keys import create_identity
from authsome.store.local import LocalAppStore


def test_init_removes_legacy_default_state_and_registers_identity(
    runner: CliRunner,
    mock_client: MagicMock,
    tmp_path: Path,
) -> None:
    identities = tmp_path / "identities"
    identities.mkdir(parents=True)
    (identities / "default.json").write_text("{}", encoding="utf-8")
    (identities / "default.key").write_text("legacy\n", encoding="utf-8")

    asyncio.run(LocalAppStore(tmp_path).ensure_initialized())

    result = runner.invoke(cli, ["--log-file", "", "init", "--json"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["profile"] != "default"
    assert data["registration_status"] == "registered"
    assert not (identities / "default.json").exists()
    assert not (identities / "default.key").exists()
    mock_client.register_identity.assert_called_once_with(data["profile"], data["did"])

    config_data = load_client_config(tmp_path)
    assert config_data.active_identity == data["profile"]


def test_init_skips_registration_for_registered_active_profile(
    runner: CliRunner,
    mock_client: MagicMock,
    tmp_path: Path,
) -> None:
    asyncio.run(LocalAppStore(tmp_path).ensure_initialized())
    identity = create_identity(tmp_path, "steady-wisely-boldly-0042")
    mark_registered(tmp_path, identity.handle)
    save_client_config(tmp_path, ClientConfig(active_identity=identity.handle))

    result = runner.invoke(cli, ["--log-file", "", "init", "--json"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["profile"] == identity.handle
    mock_client.register_identity.assert_not_called()
