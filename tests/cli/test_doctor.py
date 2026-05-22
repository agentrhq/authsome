"""Tests for the `authsome advanced doctor` command output and logic."""

import json
from unittest.mock import patch

from click.testing import CliRunner

from authsome.cli.main import cli


class TestDoctorCommand:
    """Tests for the `authsome advanced doctor` CLI command."""

    def test_doctor_success_rendering(self, runner: CliRunner) -> None:
        """Verifies OK state renders successfully."""
        mock_results = {
            "status": "ready",
            "checks": {"config": "ok", "integrity": "ok", "file_permissions": "ok"},
            "issues": [],
            "warnings": [],
        }

        with patch("authsome.cli.context.CliRuntime.doctor", return_value=mock_results):
            result = runner.invoke(cli, ["--log-file", "", "advanced", "doctor"])

        assert result.exit_code == 0
        assert "config: OK" in result.output
        assert "integrity: OK" in result.output
        assert "file_permissions: OK" in result.output

    def test_doctor_warnings_rendering(self, runner: CliRunner) -> None:
        """Verifies that non-critical warnings display and allow 0 exit code."""
        mock_results = {
            "status": "ready",
            "checks": {"connections": "ok", "key_age": "ok"},
            "issues": [],
            "warnings": ["master.key too old", "no connections"],
        }

        with patch("authsome.cli.context.CliRuntime.doctor", return_value=mock_results):
            result = runner.invoke(cli, ["--log-file", "", "advanced", "doctor"])

        assert result.exit_code == 0
        assert "Warnings:" in result.output
        assert "master.key too old" in result.output
        assert "no connections" in result.output

    def test_doctor_failure_rendering(self, runner: CliRunner) -> None:
        """Verifies that actual failures cause exit code 1 and list issues."""
        mock_results = {
            "status": "not_ready",
            "checks": {
                "config": "failed",
            },
            "issues": ["config schema mismatch"],
            "warnings": [],
        }

        with patch("authsome.cli.context.CliRuntime.doctor", return_value=mock_results):
            result = runner.invoke(cli, ["--log-file", "", "advanced", "doctor"])

        assert result.exit_code == 1
        assert "config: FAIL" in result.output
        assert "Issues found:" in result.output
        assert "config schema mismatch" in result.output

    def test_doctor_json_format(self, runner: CliRunner) -> None:
        """Validates raw backend passthrough in json mode."""
        mock_results = {"status": "ready", "checks": {"x": "ok"}, "issues": [], "warnings": ["caution"]}

        with patch("authsome.cli.context.CliRuntime.doctor", return_value=mock_results):
            result = runner.invoke(cli, ["--log-file", "", "advanced", "doctor", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        # Verify wrapper fields and inner content
        assert data["v"] == 1
        assert data["status"] == "ready"
        assert "caution" in data["warnings"]
