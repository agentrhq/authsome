"""Tests for the `authsome daemon` subgroup.

Covers: daemon status JSON output, start/stop calls, and logs command
when no log file exists.
"""

import json
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from authsome.cli.main import cli


class TestDaemonStatusCommand:
    """Tests for `authsome daemon status`."""

    def test_status_json_output(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("authsome.cli.main.daemon_status") as mock_status:
            mock_status.return_value = {
                "running": True,
                "pid_file": "/tmp/daemon.pid",
                "log_file": "/tmp/daemon.log",
            }
            result = runner.invoke(cli, ["--log-file", "", "daemon", "status", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["running"] is True

    def test_status_human_output(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("authsome.cli.main.daemon_status") as mock_status:
            mock_status.return_value = {
                "running": False,
                "error": "Connection refused",
                "pid_file": "/tmp/daemon.pid",
                "log_file": "/tmp/daemon.log",
            }
            result = runner.invoke(cli, ["--log-file", "", "daemon", "status"])
        assert result.exit_code == 0
        assert "running" in result.output.lower() or "Connection refused" in result.output


class TestDaemonStartStopCommand:
    """Tests for `authsome daemon start` and `authsome daemon stop`."""

    def test_daemon_start_calls_start_daemon(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with (
            patch("authsome.cli.main.start_daemon") as mock_start,
            patch("authsome.cli.main.wait_for_daemon_ready"),
            patch("authsome.cli.main.is_daemon_responsive", return_value=False),
            patch("authsome.cli.main.is_port_occupied", return_value=False),
        ):
            result = runner.invoke(cli, ["--log-file", "", "daemon", "start"])
        assert result.exit_code == 0
        mock_start.assert_called_once()

    def test_daemon_stop_calls_stop_daemon(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with patch("authsome.cli.main.stop_daemon") as mock_stop:
            mock_stop.return_value = (True, "Daemon stopped successfully.")
            result = runner.invoke(cli, ["--log-file", "", "daemon", "stop"])
        assert result.exit_code == 0
        mock_stop.assert_called_once()

    def test_daemon_restart_calls_both(self, runner: CliRunner, mock_client: MagicMock) -> None:
        with (
            patch("authsome.cli.main.stop_daemon") as mock_stop,
            patch("authsome.cli.main.start_daemon") as mock_start,
            patch("authsome.cli.main.wait_for_daemon_ready"),
            patch("authsome.cli.main.is_daemon_responsive", return_value=False),
            patch("authsome.cli.main.is_port_occupied", return_value=False),
        ):
            mock_stop.return_value = (True, "Daemon stopped successfully.")
            result = runner.invoke(cli, ["--log-file", "", "daemon", "restart"])
        assert result.exit_code == 0
        mock_stop.assert_called_once()
        mock_start.assert_called_once()


class TestDaemonLogsCommand:
    """Tests for `authsome daemon logs`."""

    def test_logs_no_file_prints_message(self, runner: CliRunner, mock_client: MagicMock, tmp_path) -> None:
        with patch("authsome.cli.daemon_control.LOG_FILE", tmp_path / "nonexistent.log"):
            result = runner.invoke(cli, ["--log-file", "", "daemon", "logs"])
        assert result.exit_code == 0
        assert "No daemon log" in result.output

    def test_logs_shows_last_n_lines(self, runner: CliRunner, mock_client: MagicMock, tmp_path) -> None:
        log_file = tmp_path / "daemon.log"
        lines = [f"line {i}\n" for i in range(1, 101)]
        log_file.write_text("".join(lines), encoding="utf-8")

        with patch("authsome.cli.daemon_control.LOG_FILE", log_file):
            result = runner.invoke(cli, ["--log-file", "", "daemon", "logs", "-n", "5"])
        assert result.exit_code == 0
        # Should show last 5 lines
        assert "line 100" in result.output
        assert "line 96" in result.output
        assert "line 95" not in result.output
