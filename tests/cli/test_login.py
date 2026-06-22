"""Tests for `authsome login`."""

# ruff: noqa: PLR2004

import json

from authsome.cli.main import cli


def _started_session(session_id: str = "sess-123") -> dict:
    return {
        "id": session_id,
        "status": "pending",
        "next_action": {
            "type": "open_url",
            "url": "https://auth.example.com/oauth?state=xyz",
        },
    }


def _completed_session(session_id: str = "sess-456") -> dict:
    return {
        "id": session_id,
        "status": "completed",
        "next_action": {"type": "none"},
    }


class TestLoginCommand:
    """Tests for `authsome login <provider>`."""

    def test_started_flow_returns_json(self, runner, mock_client) -> None:
        mock_client.start_login.return_value = _started_session()
        result = runner.invoke(cli, ["--log-file", "", "login", "github", "--connection", "work"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["provider"] == "github"
        assert data["status"] == "started"

    def test_completed_flow_returns_json(self, runner, mock_client) -> None:
        mock_client.start_login.return_value = _completed_session()
        result = runner.invoke(cli, ["--log-file", "", "login", "openai", "--connection", "work"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["provider"] == "openai"
        assert data["status"] == "success"

    def test_force_flag_still_returns_json(self, runner, mock_client) -> None:
        mock_client.start_login.return_value = _started_session()
        result = runner.invoke(cli, ["--log-file", "", "login", "github", "--connection", "work", "--force"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "started"

    def test_force_flag_quiet_returns_json(self, runner, mock_client) -> None:
        mock_client.start_login.return_value = _started_session()
        result = runner.invoke(cli, ["--log-file", "", "login", "github", "--connection", "work", "--force", "--quiet"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "started"

    def test_start_login_called_with_provider(self, runner, mock_client) -> None:
        mock_client.start_login.return_value = _started_session()
        runner.invoke(cli, ["--log-file", "", "login", "github", "--connection", "work"])
        mock_client.start_login.assert_called_once()
        kwargs = mock_client.start_login.call_args.kwargs
        assert kwargs["provider"] == "github"

    def test_connection_option_passed_through(self, runner, mock_client) -> None:
        mock_client.start_login.return_value = _started_session()
        runner.invoke(cli, ["--log-file", "", "login", "github", "--connection", "work"])
        kwargs = mock_client.start_login.call_args.kwargs
        assert kwargs["connection"] == "work"

    def test_scopes_option_parsed_as_list(self, runner, mock_client) -> None:
        mock_client.start_login.return_value = _started_session()
        runner.invoke(cli, ["--log-file", "", "login", "github", "--connection", "work", "--scopes", "repo,read:user"])
        kwargs = mock_client.start_login.call_args.kwargs
        assert kwargs["scopes"] == ["repo", "read:user"]

    def test_login_requires_connection_in_non_interactive_context(self, runner, mock_client) -> None:
        result = runner.invoke(cli, ["--log-file", "", "login", "github"])
        assert result.exit_code != 0
        mock_client.start_login.assert_not_called()

    def test_login_rejects_reserved_default_connection(self, runner, mock_client) -> None:
        result = runner.invoke(cli, ["--log-file", "", "login", "github", "--connection", "default"])
        assert result.exit_code != 0
        mock_client.start_login.assert_not_called()

    def test_login_failure_exits_4(self, runner, mock_client) -> None:
        from authsome.errors import ProviderNotFoundError

        mock_client.start_login.side_effect = ProviderNotFoundError("nope")
        result = runner.invoke(cli, ["--log-file", "", "login", "nope", "--connection", "work"])
        assert result.exit_code == 4
        data = json.loads(result.output)
        assert data["error"] == "ProviderNotFoundError"
