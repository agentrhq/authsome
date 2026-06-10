"""Tests for `authsome provider list`."""

import json

from authsome.cli.main import cli


def _make_list_response(
    bundled: list[dict] | None = None,
    custom: list[dict] | None = None,
    connections: list[dict] | None = None,
    global_connections: list[dict] | None = None,
) -> dict:
    bundled = bundled or []
    custom = custom or []
    connections = connections or []
    global_connections = global_connections or []
    return {
        "connections": connections,
        "global_connections": global_connections,
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

    def test_json_output_includes_global_connections(self, runner, mock_client) -> None:
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
            global_connections=[
                {
                    "provider": "openai",
                    "provider_display_name": "OpenAI",
                    "connection_name": "default",
                    "status": "connected",
                    "auth_type": "api_key",
                    "account_label": "Team OpenAI",
                    "source": "global",
                }
            ],
        )

        result = runner.invoke(cli, ["--log-file", "", "provider", "list"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["bundled"][0]["connections"] == []
        assert data["bundled"][0]["global_connections"][0]["source"] == "global"

    def test_provider_inspect_includes_matching_global_connections(self, runner, mock_client) -> None:
        provider_def = {
            "name": "openai",
            "display_name": "OpenAI",
            "auth_type": "api_key",
            "flow": "api_key",
            "schema_version": 1,
            "api_key": {"header_name": "Authorization", "header_prefix": "Bearer"},
        }
        mock_client.get_provider.return_value = provider_def.copy()
        mock_client.list_connections.return_value = _make_list_response(
            bundled=[provider_def],
            global_connections=[
                {
                    "provider": "openai",
                    "provider_display_name": "OpenAI",
                    "connection_name": "default",
                    "status": "connected",
                    "auth_type": "api_key",
                    "account_label": "Team OpenAI",
                    "source": "global",
                }
            ],
        )

        result = runner.invoke(cli, ["--log-file", "", "provider", "inspect", "openai"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["connections"] == []
        assert data["global_connections"][0]["connection_name"] == "default"

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
