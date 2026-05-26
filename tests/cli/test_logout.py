"""Tests for `authsome logout`."""

import json

from authsome.cli.main import cli


class TestLogoutCommand:
    """Tests for `authsome logout <provider>`."""

    def test_logout_returns_json(self, runner, mock_client) -> None:
        result = runner.invoke(cli, ["--log-file", "", "logout", "github"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["status"] == "logged_out"
        assert data["provider"] == "github"
        assert data["connection"] == "default"

    def test_logout_connection_option(self, runner, mock_client) -> None:
        result = runner.invoke(cli, ["--log-file", "", "logout", "github", "--connection", "work"])
        assert result.exit_code == 0
        mock_client.logout.assert_called_once_with("github", "work")

    def test_logout_calls_client(self, runner, mock_client) -> None:
        runner.invoke(cli, ["--log-file", "", "logout", "openai"])
        mock_client.logout.assert_called_once_with("openai", "default")

    def test_logout_provider_not_found_exits_4(self, runner, mock_client) -> None:
        from authsome.errors import ProviderNotFoundError

        mock_client.logout.side_effect = ProviderNotFoundError("nope")
        result = runner.invoke(cli, ["--log-file", "", "logout", "nope"])
        assert result.exit_code == 4
        data = json.loads(result.output)
        assert data["error"] == "ProviderNotFoundError"
