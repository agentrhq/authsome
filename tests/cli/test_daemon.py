"""Tests for the `authsome admin daemon` subgroup."""

import json
from unittest.mock import patch

from authsome.cli.main import cli


class TestDaemonStatusCommand:
    """Tests for `authsome admin daemon status`."""

    def test_status_json_output(self, runner, mock_client) -> None:
        with patch("authsome.cli.admin.daemon_status") as mock_status:
            mock_status.return_value = {
                "running": True,
                "pid_file": "/tmp/daemon.pid",
                "log_file": "/tmp/daemon.log",
            }
            result = runner.invoke(cli, ["--log-file", "", "admin", "daemon", "status"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["running"] is True


class TestDaemonStartStopCommand:
    """Tests for `authsome admin daemon start` and `authsome admin daemon stop`."""

    def test_daemon_start_calls_start_daemon(self, runner, mock_client) -> None:
        with (
            patch("authsome.cli.admin.start_daemon") as mock_start,
            patch("authsome.cli.admin.wait_for_daemon_ready"),
            patch("authsome.cli.admin.is_daemon_responsive", return_value=False),
            patch("authsome.cli.admin.is_port_occupied", return_value=False),
        ):
            result = runner.invoke(cli, ["--log-file", "", "admin", "daemon", "start"])
        assert result.exit_code == 0
        mock_start.assert_called_once()
        data = json.loads(result.output)
        assert data["status"] == "started"

    def test_daemon_stop_calls_stop_daemon(self, runner, mock_client) -> None:
        with patch("authsome.cli.admin.stop_daemon") as mock_stop:
            mock_stop.return_value = (True, "Daemon stopped successfully.")
            result = runner.invoke(cli, ["--log-file", "", "admin", "daemon", "stop"])
        assert result.exit_code == 0
        mock_stop.assert_called_once()
        data = json.loads(result.output)
        assert data["status"] == "stopped"

    def test_daemon_restart_calls_both(self, runner, mock_client) -> None:
        with (
            patch("authsome.cli.admin.stop_daemon") as mock_stop,
            patch("authsome.cli.admin.start_daemon") as mock_start,
            patch("authsome.cli.admin.wait_for_daemon_ready"),
            patch("authsome.cli.admin.is_daemon_responsive", return_value=False),
            patch("authsome.cli.admin.is_port_occupied", return_value=False),
        ):
            mock_stop.return_value = (True, "Daemon stopped successfully.")
            result = runner.invoke(cli, ["--log-file", "", "admin", "daemon", "restart"])
        assert result.exit_code == 0
        mock_stop.assert_called_once()
        mock_start.assert_called_once()
        data = json.loads(result.output)
        assert data["status"] == "restarted"


class TestDaemonLogsCommand:
    """Tests for `authsome admin daemon logs`."""

    def test_logs_no_file_returns_empty_entries(self, runner, mock_client, tmp_path) -> None:
        with patch("authsome.cli.daemon_control.LOG_FILE", tmp_path / "nonexistent.log"):
            result = runner.invoke(cli, ["--log-file", "", "admin", "daemon", "logs"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["entries"] == []

    def test_logs_shows_last_n_lines(self, runner, mock_client, tmp_path) -> None:
        log_file = tmp_path / "daemon.log"
        lines = [f"line {i}\n" for i in range(1, 101)]
        log_file.write_text("".join(lines), encoding="utf-8")

        with patch("authsome.cli.daemon_control.LOG_FILE", log_file):
            result = runner.invoke(cli, ["--log-file", "", "admin", "daemon", "logs", "-n", "5"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "line 100" in data["entries"][-1]
        assert "line 96" in data["entries"][0]
