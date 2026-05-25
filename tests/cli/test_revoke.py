"""Tests for `authsome provider revoke`.

Covers: success output, JSON output, and client call verification.
"""

import json
from unittest.mock import MagicMock

from click.testing import CliRunner

from authsome.cli.main import cli


class TestRevokeCommand:
    """Tests for `authsome provider revoke <provider>`."""

    def test_revoke_exits_0(self, runner: CliRunner, mock_client: MagicMock) -> None:
        result = runner.invoke(cli, ["--log-file", "", "provider", "revoke", "github"])
        assert result.exit_code == 0, result.output

    def test_revoke_human_output(self, runner: CliRunner, mock_client: MagicMock) -> None:
        result = runner.invoke(cli, ["--log-file", "", "provider", "revoke", "github"])
        assert "github" in result.output
        assert "revoked" in result.output.lower() or "Revoked" in result.output

    def test_revoke_json_output(self, runner: CliRunner, mock_client: MagicMock) -> None:
        result = runner.invoke(cli, ["--log-file", "", "provider", "revoke", "openai", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "revoked"
        assert data["provider"] == "openai"

    def test_revoke_calls_client(self, runner: CliRunner, mock_client: MagicMock) -> None:
        runner.invoke(cli, ["--log-file", "", "provider", "revoke", "openai"])
        mock_client.revoke.assert_called_once_with("openai")

    def test_revoke_provider_not_found_exits_4(self, runner: CliRunner, mock_client: MagicMock) -> None:
        from authsome.errors import ProviderNotFoundError

        mock_client.revoke.side_effect = ProviderNotFoundError("unknown")
        result = runner.invoke(cli, ["--log-file", "", "provider", "revoke", "unknown"])
        assert result.exit_code == 4

    def test_revoke_operation_not_allowed_exits_4(self, runner: CliRunner, mock_client: MagicMock) -> None:
        from authsome.errors import OperationNotAllowedError

        mock_client.revoke.side_effect = OperationNotAllowedError(
            "revoke",
            "revoke is not allowed in hosted deployments",
        )
        result = runner.invoke(cli, ["--log-file", "", "provider", "revoke", "openai"])
        assert result.exit_code == 4
        assert "OperationNotAllowedError" in result.output
