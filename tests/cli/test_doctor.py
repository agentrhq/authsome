"""Tests for the `authsome doctor` command."""

import json
from unittest.mock import patch

from authsome.cli.main import cli


class TestDoctorCommand:
    """Tests for the `authsome doctor` CLI command."""

    def test_doctor_success_returns_json(self, runner) -> None:
        mock_results = {
            "status": "ready",
            "checks": {"config": "ok", "integrity": "ok", "file_permissions": "ok"},
            "issues": [],
            "warnings": [],
        }

        with patch("authsome.cli.context.CliRuntime.doctor", return_value=mock_results):
            result = runner.invoke(cli, ["--log-file", "", "doctor"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["status"] == "ready"
        assert data["checks"]["config"] == "ok"

    def test_doctor_warnings_return_json(self, runner) -> None:
        mock_results = {
            "status": "ready",
            "checks": {"connections": "ok", "key_age": "ok"},
            "issues": [],
            "warnings": ["master.key too old", "no connections"],
        }

        with patch("authsome.cli.context.CliRuntime.doctor", return_value=mock_results):
            result = runner.invoke(cli, ["--log-file", "", "doctor"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "master.key too old" in data["warnings"]
        assert "no connections" in data["warnings"]

    def test_doctor_failure_returns_json_and_exit_1(self, runner) -> None:
        mock_results = {
            "status": "not_ready",
            "checks": {"config": "failed"},
            "issues": ["config schema mismatch"],
            "warnings": [],
        }

        with patch("authsome.cli.context.CliRuntime.doctor", return_value=mock_results):
            result = runner.invoke(cli, ["--log-file", "", "doctor"])

        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["status"] == "not_ready"
        assert data["issues"] == ["config schema mismatch"]

    def test_json_flag_removed(self, runner) -> None:
        result = runner.invoke(cli, ["--log-file", "", "doctor", "--json"])
        assert result.exit_code == 2
        assert "No such option '--json'" in result.output
