import json

from authsome.cli.main import cli


def test_connections_set_global_outputs_server_response(runner, mock_client) -> None:
    mock_client.set_global_connection.return_value = {
        "status": "ok",
        "provider": "github",
        "connection_name": "default",
    }

    result = runner.invoke(cli, ["--log-file", "", "connections", "set-global", "github", "default"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {"status": "ok", "provider": "github", "connection_name": "default", "v": 1}
    mock_client.set_global_connection.assert_awaited_once_with("github", "default")


def test_connections_unset_global_outputs_server_response(runner, mock_client) -> None:
    mock_client.unset_global_connection.return_value = {
        "status": "ok",
        "provider": "github",
        "deleted": True,
    }

    result = runner.invoke(cli, ["--log-file", "", "connections", "unset-global", "github"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {"status": "ok", "provider": "github", "deleted": True, "v": 1}
    mock_client.unset_global_connection.assert_awaited_once_with("github")
