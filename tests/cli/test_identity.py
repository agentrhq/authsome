"""Tests for `authsome profile` commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from click.testing import CliRunner

from authsome.cli.main import cli
from authsome.identity.client_config import load_client_config
from authsome.identity.keys import load_identity


class TestProfileCommands:
    """Tests for local profile management commands."""

    def test_profile_create_writes_local_keypair(
        self, runner: CliRunner, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        result = runner.invoke(
            cli,
            ["--log-file", "", "profile", "create", "--handle", "steady-wisely-boldly-0042", "--json"],
        )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["status"] == "created"
        assert data["profile"] == "steady-wisely-boldly-0042"
        assert data["switched"] is True
        stored = load_identity(tmp_path, "steady-wisely-boldly-0042")
        assert stored.did == data["did"]
        assert load_client_config(tmp_path).active_identity == stored.handle

    def test_profile_create_switches_active_profile(
        self, runner: CliRunner, mock_client: MagicMock, tmp_path: Path
    ) -> None:
        runner.invoke(cli, ["--log-file", "", "profile", "create", "--handle", "steady-wisely-boldly-0042"])
        result = runner.invoke(
            cli,
            ["--log-file", "", "profile", "create", "--handle", "rapid-brightly-firmly-0007", "--json"],
        )

        data = json.loads(result.output)
        assert result.exit_code == 0, result.output
        assert data["status"] == "created"
        assert data["profile"] == "rapid-brightly-firmly-0007"
        assert data["switched"] is True
        assert load_client_config(tmp_path).active_identity == "rapid-brightly-firmly-0007"

    def test_profile_use_sets_active_identity(self, runner: CliRunner, mock_client: MagicMock, tmp_path: Path) -> None:
        runner.invoke(cli, ["--log-file", "", "profile", "create", "--handle", "steady-wisely-boldly-0042"])
        runner.invoke(cli, ["--log-file", "", "profile", "create", "--handle", "rapid-brightly-firmly-0007"])
        stored = load_identity(tmp_path, "steady-wisely-boldly-0042")

        result = runner.invoke(cli, ["--log-file", "", "profile", "use", "steady-wisely-boldly-0042", "--json"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["status"] == "active"
        assert data["profile"] == stored.handle
        assert data["did"] == stored.did
        assert load_client_config(tmp_path).active_identity == stored.handle
