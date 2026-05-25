"""Tests for `authsome provider list`.

Verifies JSON output shape, human-readable table rendering,
empty state, and the connected-count summary line.
"""

from unittest.mock import MagicMock

from click.testing import CliRunner

from authsome.cli.main import cli


def _bundled_provider(name: str, display_name: str, auth_type: str, connections: list) -> dict:
    return {
        "name": name,
        "display_name": display_name,
        "auth_type": auth_type,
        "flow": "api_key" if auth_type == "api_key" else "dcr_pkce",
        "schema_version": 1,
        "api_key": {"header_name": "Authorization", "header_prefix": "Bearer"} if auth_type == "api_key" else None,
        "oauth": (
            {
                "authorization_url": "https://example.com/auth",
                "token_url": "https://example.com/token",
                "scopes": [],
            }
            if auth_type == "oauth2"
            else None
        ),
    }, connections


def _make_list_response(
    bundled: list[dict] | None = None,
    custom: list[dict] | None = None,
    connections: list[dict] | None = None,
) -> dict:
    """Build the dict that list_connections() returns."""
    bundled = bundled or []
    custom = custom or []
    connections = connections or []
    return {
        "connections": connections,
        "by_source": {"bundled": bundled, "custom": custom},
    }


class TestListCommand:
    """Tests for the provider list command."""

    def test_empty_providers_prints_message(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.list_connections.return_value = _make_list_response()
        result = runner.invoke(cli, ["--log-file", "", "provider", "list"])
        assert result.exit_code == 0
        assert "No providers configured" in result.output

    def test_json_output_shape(self, runner: CliRunner, mock_client: MagicMock) -> None:
        import json

        provider_def = {
            "name": "openai",
            "display_name": "OpenAI",
            "auth_type": "api_key",
            "flow": "api_key",
            "schema_version": 1,
            "api_key": {"header_name": "Authorization", "header_prefix": "Bearer"},
        }
        mock_client.list_connections.return_value = _make_list_response(
            bundled=[provider_def],
            connections=[
                {
                    "name": "openai",
                    "default_connection": "default",
                    "connections": [
                        {
                            "connection_name": "default",
                            "is_default": True,
                            "auth_type": "api_key",
                            "status": "connected",
                        }
                    ],
                }
            ],
        )
        result = runner.invoke(cli, ["--log-file", "", "provider", "list", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert "bundled" in data
        assert "custom" in data
        assert data["bundled"][0]["name"] == "openai"

    def test_human_table_shows_provider(self, runner: CliRunner, mock_client: MagicMock) -> None:
        provider_def = {
            "name": "openai",
            "display_name": "OpenAI",
            "auth_type": "api_key",
            "flow": "api_key",
            "schema_version": 1,
            "api_key": {"header_name": "Authorization", "header_prefix": "Bearer"},
        }
        mock_client.list_connections.return_value = _make_list_response(
            bundled=[provider_def],
            connections=[
                {
                    "name": "openai",
                    "default_connection": "default",
                    "connections": [],
                }
            ],
        )
        result = runner.invoke(cli, ["--log-file", "", "provider", "list", "--no-color"])
        assert result.exit_code == 0, result.output
        assert "OpenAI" in result.output
        assert "openai" in result.output

    def test_connected_count_in_summary(self, runner: CliRunner, mock_client: MagicMock) -> None:
        from datetime import UTC, datetime, timedelta

        future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        provider_def = {
            "name": "github",
            "display_name": "GitHub",
            "auth_type": "oauth2",
            "flow": "dcr_pkce",
            "schema_version": 1,
            "oauth": {
                "authorization_url": "https://github.com/login/oauth/authorize",
                "token_url": "https://github.com/login/oauth/access_token",
                "scopes": [],
            },
        }
        mock_client.list_connections.return_value = _make_list_response(
            bundled=[provider_def],
            connections=[
                {
                    "name": "github",
                    "default_connection": "default",
                    "connections": [
                        {
                            "connection_name": "default",
                            "is_default": True,
                            "auth_type": "oauth2",
                            "status": "connected",
                            "expires_at": future,
                        }
                    ],
                }
            ],
        )
        result = runner.invoke(cli, ["--log-file", "", "provider", "list", "--no-color"])
        assert result.exit_code == 0, result.output
        assert "1 connected" in result.output

    def test_not_connected_shows_in_table(self, runner: CliRunner, mock_client: MagicMock) -> None:
        provider_def = {
            "name": "linear",
            "display_name": "Linear",
            "auth_type": "oauth2",
            "flow": "dcr_pkce",
            "schema_version": 1,
            "oauth": {
                "authorization_url": "https://linear.app/oauth/authorize",
                "token_url": "https://linear.app/oauth/token",
                "scopes": [],
            },
        }
        mock_client.list_connections.return_value = _make_list_response(
            bundled=[provider_def],
            connections=[
                {
                    "name": "linear",
                    "default_connection": "default",
                    "connections": [],
                }
            ],
        )
        result = runner.invoke(cli, ["--log-file", "", "provider", "list", "--no-color"])
        assert result.exit_code == 0, result.output
        assert "not_connected" in result.output

    def test_no_color_flag_respected(self, runner: CliRunner, mock_client: MagicMock) -> None:
        provider_def = {
            "name": "openai",
            "display_name": "OpenAI",
            "auth_type": "api_key",
            "flow": "api_key",
            "schema_version": 1,
            "api_key": {"header_name": "Authorization", "header_prefix": "Bearer"},
        }
        mock_client.list_connections.return_value = _make_list_response(
            bundled=[provider_def],
            connections=[{"name": "openai", "default_connection": "default", "connections": []}],
        )
        result = runner.invoke(cli, ["--log-file", "", "provider", "list", "--no-color"])
        assert result.exit_code == 0
        # ANSI escape codes should not appear in no-color output
        assert "\x1b[" not in result.output
