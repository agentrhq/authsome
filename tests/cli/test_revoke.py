"""Tests for `authsome provider revoke`."""

import json

from authsome.cli.main import cli


class TestRevokeCommand:
    """Tests for `authsome provider revoke <provider>`."""

    def test_revoke_returns_json(self, runner, mock_client) -> None:
        result = runner.invoke(cli, ["--log-file", "", "provider", "revoke", "github"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["status"] == "revoked"
        assert data["provider"] == "github"

    def test_revoke_calls_client(self, runner, mock_client) -> None:
        runner.invoke(cli, ["--log-file", "", "provider", "revoke", "openai"])
        mock_client.revoke.assert_called_once_with("openai")

    def test_revoke_provider_not_found_exits_4(self, runner, mock_client) -> None:
        from authsome.errors import ProviderNotFoundError

        mock_client.revoke.side_effect = ProviderNotFoundError("unknown")
        result = runner.invoke(cli, ["--log-file", "", "provider", "revoke", "unknown"])
        assert result.exit_code == 4

    def test_revoke_operation_not_allowed_exits_4(self, runner, mock_client) -> None:
        from authsome.errors import OperationNotAllowedError

        mock_client.revoke.side_effect = OperationNotAllowedError(
            "revoke",
            "revoke requires an admin principal",
        )
        result = runner.invoke(cli, ["--log-file", "", "provider", "revoke", "openai"])
        assert result.exit_code == 4
        data = json.loads(result.output)
        assert data["error"] == "OperationNotAllowedError"
