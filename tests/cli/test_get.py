"""Tests for `authsome get`.

Covers: JSON output, --field extraction, provider-not-found (exit 4),
connection-not-found (exit 3), and field-not-found (exit 1).
"""

import json
from unittest.mock import MagicMock

from click.testing import CliRunner

from authsome.cli.main import cli
from authsome.errors import ConnectionNotFoundError, ProviderNotFoundError


def _make_connection_record() -> dict:
    return {
        "schema_version": 2,
        "provider": "openai",
        "identity": "default",
        "connection_name": "default",
        "auth_type": "api_key",
        "status": "connected",
        "api_key": "sk-secret",
        "access_token": None,
        "refresh_token": None,
        "expires_at": None,
        "scopes": [],
        "token_type": None,
        "base_url": None,
        "host_url": None,
    }


class TestGetCommand:
    """Tests for `authsome get <provider>`."""

    def test_json_output_contains_record_fields(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get_provider.return_value = {"name": "openai"}
        mock_client.get_connection.return_value = _make_connection_record()

        result = runner.invoke(cli, ["--log-file", "", "get", "openai", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["provider"] == "openai"
        assert data["status"] == "connected"

    def test_sensitive_fields_redacted_by_default(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get_provider.return_value = {"name": "openai"}
        mock_client.get_connection.return_value = _make_connection_record()

        result = runner.invoke(cli, ["--log-file", "", "get", "openai", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["api_key"] == "***REDACTED***"

    def test_field_extraction(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get_provider.return_value = {"name": "openai"}
        mock_client.get_connection.return_value = _make_connection_record()

        result = runner.invoke(cli, ["--log-file", "", "get", "openai", "--field", "status"])
        assert result.exit_code == 0, result.output
        assert "connected" in result.output

    def test_field_extraction_json(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get_provider.return_value = {"name": "openai"}
        mock_client.get_connection.return_value = _make_connection_record()

        result = runner.invoke(cli, ["--log-file", "", "get", "openai", "--field", "provider", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == {"provider": "openai", "v": 1}

    def test_unknown_field_exits_1(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get_provider.return_value = {"name": "openai"}
        mock_client.get_connection.return_value = _make_connection_record()

        result = runner.invoke(cli, ["--log-file", "", "get", "openai", "--field", "nonexistent"])
        assert result.exit_code == 1

    def test_provider_not_found_exits_4(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get_provider.side_effect = ProviderNotFoundError("unknown")

        result = runner.invoke(cli, ["--log-file", "", "get", "unknown"])
        assert result.exit_code == 4

    def test_connection_not_found_exits_3(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get_provider.return_value = {"name": "openai"}
        mock_client.get_connection.side_effect = ConnectionNotFoundError(
            provider="openai", connection="missing", identity="default"
        )

        result = runner.invoke(cli, ["--log-file", "", "get", "openai", "--connection", "missing"])
        assert result.exit_code == 3

    def test_human_output_shows_key_value_pairs(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.get_provider.return_value = {"name": "openai"}
        mock_client.get_connection.return_value = _make_connection_record()

        result = runner.invoke(cli, ["--log-file", "", "get", "openai"])
        assert result.exit_code == 0
        assert "provider: openai" in result.output
        assert "status: connected" in result.output
