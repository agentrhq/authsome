"""Tests for `authsome whoami`.

Covers: JSON output shape, vault OK and FAIL status rendering,
and connected providers count.
"""

import json
from unittest.mock import MagicMock

from click.testing import CliRunner

from authsome.cli.main import cli


def _make_whoami(version: str = "1.2.3") -> dict:
    return {
        "version": version,
        "home": "/home/test/.authsome",
        "identity": "steady-wisely-boldly-0042",
        "did": "did:key:z6MkTest",
        "registration_status": "registered",
        "encryption_backend": "local_key",
    }


def _make_ready_ok() -> dict:
    return {"status": "ready", "checks": {"vault": "ok"}, "issues": []}


def _make_ready_fail() -> dict:
    return {"status": "not_ready", "checks": {"vault": "error"}, "issues": ["vault corrupted"]}


class TestWhoamiCommand:
    """Tests for `authsome whoami`."""

    def test_json_output_shape(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.whoami.return_value = _make_whoami()
        mock_client.doctor.return_value = _make_ready_ok()
        mock_client.list_connections.return_value = {"connections": [], "by_source": {"bundled": [], "custom": []}}

        result = runner.invoke(cli, ["--log-file", "", "whoami", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["authsome_version"] == "1.2.3"
        assert data["profile"] == "steady-wisely-boldly-0042"
        assert data["vault_status"] == "OK"
        assert "connected_providers_count" in data
        assert "connected_providers" in data

    def test_vault_fail_shown_in_json(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.whoami.return_value = _make_whoami()
        mock_client.doctor.return_value = _make_ready_fail()
        mock_client.list_connections.return_value = {"connections": [], "by_source": {"bundled": [], "custom": []}}

        result = runner.invoke(cli, ["--log-file", "", "whoami", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["vault_status"] == "ERROR"

    def test_human_output_shows_version(self, runner: CliRunner, mock_client: MagicMock) -> None:
        mock_client.whoami.return_value = _make_whoami("2.0.0")
        mock_client.doctor.return_value = _make_ready_ok()
        mock_client.list_connections.return_value = {"connections": [], "by_source": {"bundled": [], "custom": []}}

        result = runner.invoke(cli, ["--log-file", "", "whoami", "--no-color"])
        assert result.exit_code == 0
        assert "2.0.0" in result.output

    def test_connected_providers_counted(self, runner: CliRunner, mock_client: MagicMock) -> None:
        from datetime import UTC, datetime, timedelta

        future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        mock_client.whoami.return_value = _make_whoami()
        mock_client.doctor.return_value = _make_ready_ok()
        mock_client.list_connections.return_value = {
            "connections": [
                {
                    "name": "github",
                    "default_connection": "default",
                    "connections": [{"connection_name": "default", "status": "connected", "expires_at": future}],
                }
            ],
            "by_source": {"bundled": [], "custom": []},
        }

        result = runner.invoke(cli, ["--log-file", "", "whoami", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["connected_providers_count"] == 1
        assert data["connected_providers"][0]["name"] == "github"
