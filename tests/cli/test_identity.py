"""Tests for `authsome agent` commands."""

import json
from pathlib import Path

from authsome.cli.config import ClientConfig
from authsome.cli.identity import RuntimeIdentity
from authsome.cli.main import cli


class TestAgentCommands:
    """Tests for local agent management commands."""

    def test_root_help_shows_agent_not_legacy_profile(self, runner) -> None:
        result = runner.invoke(cli, ["--log-file", "", "--help"])

        assert result.exit_code == 0, result.output
        assert "agent" in result.output
        assert "profile" not in result.output

    def test_profile_command_is_removed(self, runner) -> None:
        result = runner.invoke(cli, ["--log-file", "", "profile", "--help"])

        assert result.exit_code != 0
        assert "No such command 'profile'" in result.output

    def test_agent_create_writes_local_keypair(self, runner, mock_client, tmp_path: Path) -> None:
        result = runner.invoke(
            cli,
            ["--log-file", "", "agent", "create", "--handle", "steady-wisely-boldly-0042"],
        )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["status"] == "created"
        assert data["agent"] == "steady-wisely-boldly-0042"
        assert data["switched"] is True
        stored = RuntimeIdentity.from_filesystem(tmp_path, "steady-wisely-boldly-0042")
        assert stored.did == data["did"]
        assert ClientConfig.load(tmp_path).active_identity == stored.handle

    def test_agent_use_sets_active_agent(self, runner, mock_client, tmp_path: Path) -> None:
        runner.invoke(cli, ["--log-file", "", "agent", "create", "--handle", "steady-wisely-boldly-0042"])
        runner.invoke(cli, ["--log-file", "", "agent", "create", "--handle", "rapid-brightly-firmly-0007"])
        stored = RuntimeIdentity.from_filesystem(tmp_path, "steady-wisely-boldly-0042")

        result = runner.invoke(cli, ["--log-file", "", "agent", "use", "steady-wisely-boldly-0042"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["status"] == "active"
        assert data["agent"] == stored.handle
        assert data["did"] == stored.did
        assert ClientConfig.load(tmp_path).active_identity == stored.handle
