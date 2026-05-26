"""Tests for `authsome provider list`."""

import json

from authsome.cli.main import cli


def _make_list_response(
    bundled: list[dict] | None = None,
    custom: list[dict] | None = None,
    connections: list[dict] | None = None,
) -> dict:
    bundled = bundled or []
    custom = custom or []
    connections = connections or []
    return {
        "connections": connections,
        "by_source": {"bundled": bundled, "custom": custom},
    }


class TestListCommand:
    """Tests for the provider list command."""

    def test_empty_providers_returns_empty_json(self, runner, mock_client) -> None:
        mock_client.list_connections.return_value = _make_list_response()
        result = runner.invoke(cli, ["--log-file", "", "provider", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["bundled"] == []
        assert data["custom"] == []

    def test_json_output_shape(self, runner, mock_client) -> None:
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
        result = runner.invoke(cli, ["--log-file", "", "provider", "list"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["bundled"][0]["name"] == "openai"
        assert data["bundled"][0]["connections"][0]["status"] == "connected"

    def test_no_color_flag_does_not_change_json(self, runner, mock_client) -> None:
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
        data = json.loads(result.output)
        assert data["bundled"][0]["name"] == "openai"
