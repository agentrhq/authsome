from click.testing import CliRunner

from authsome.cli.main import cli


def test_ui_opens_bootstrap_url(runner: CliRunner, mock_client) -> None:
    mock_client.start_ui_session.return_value = {"url": "https://authsome.example/ui/bootstrap/boot_123"}

    result = runner.invoke(cli, ["--log-file", "", "advanced", "ui"])

    assert result.exit_code == 0
    assert "https://authsome.example/ui/bootstrap/boot_123" in result.output
    mock_client.start_ui_session.assert_called_once_with()


def test_ui_no_browser_prints_bootstrap_url(runner: CliRunner, mock_client) -> None:
    mock_client.start_ui_session.return_value = {"url": "https://authsome.example/ui/bootstrap/boot_123"}

    result = runner.invoke(cli, ["--log-file", "", "advanced", "ui", "--no-browser"])

    assert result.exit_code == 0
    assert result.output.strip() == "https://authsome.example/ui/bootstrap/boot_123"
    mock_client.start_ui_session.assert_called_once_with()
