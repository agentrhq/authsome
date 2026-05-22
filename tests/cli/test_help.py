"""Tests for top-level and advanced help surfaces."""

from click.testing import CliRunner

from authsome.cli.main import cli


def test_top_level_help_hides_advanced_commands(runner: CliRunner, mock_client) -> None:
    result = runner.invoke(cli, ["--log-file", "", "--help"])

    assert result.exit_code == 0, result.output
    assert "\n  advanced" in result.output
    assert "\n  rekey" not in result.output
    assert "\n  daemon" not in result.output
    assert "\n  register" not in result.output
    assert "\n  profile" not in result.output


def test_advanced_help_lists_hidden_commands(runner: CliRunner, mock_client) -> None:
    result = runner.invoke(cli, ["--log-file", "", "advanced", "--help"])

    assert result.exit_code == 0, result.output
    assert "\n  rekey" in result.output
    assert "\n  daemon" in result.output
    assert "\n  register" in result.output
    assert "\n  profile" in result.output


def test_top_level_advanced_aliases_do_not_work(runner: CliRunner, mock_client) -> None:
    result = runner.invoke(cli, ["--log-file", "", "rekey", "--help"])

    assert result.exit_code != 0
    assert "No such command 'rekey'" in result.output
