"""Tests for `authsome register`.

Covers: --yes flag skips confirmation, file not found exits 1,
invalid JSON exits 1, HTTP-only endpoint is rejected, and
the provider definition is passed to the daemon client.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from authsome.cli.main import cli


def _write_provider(tmp_path: Path, definition: dict) -> Path:
    p = tmp_path / "provider.json"
    p.write_text(json.dumps(definition), encoding="utf-8")
    return p


_VALID_API_KEY_PROVIDER = {
    "name": "myprov",
    "display_name": "My Provider",
    "auth_type": "api_key",
    "flow": "api_key",
    "api_key": {"header_name": "Authorization"},
}

_VALID_OAUTH_PROVIDER = {
    "name": "myoauth",
    "display_name": "My OAuth",
    "auth_type": "oauth2",
    "flow": "dcr_pkce",
    "oauth": {
        "authorization_url": "https://example.com/auth",
        "token_url": "https://example.com/token",
    },
}


class TestRegisterCommand:
    """Tests for `authsome register <path>`."""

    def test_file_not_found_exits_1(self, runner: CliRunner, mock_client: MagicMock) -> None:
        result = runner.invoke(cli, ["--log-file", "", "register", "/no/such/file.json", "--yes"])
        assert result.exit_code == 1
        assert (
            "not found" in result.output.lower()
            or "not found"
            in runner.invoke(cli, ["--log-file", "", "register", "/no/such/file.json", "--yes"]).output.lower()
        )

    def test_invalid_json_exits_1(self, runner: CliRunner, mock_client: MagicMock, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("this is not json", encoding="utf-8")
        result = runner.invoke(cli, ["--log-file", "", "register", str(bad), "--yes"])
        assert result.exit_code == 1

    def test_yes_flag_skips_confirmation(
        self, runner: CliRunner, mock_client: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = _write_provider(tmp_path, _VALID_API_KEY_PROVIDER)
        confirm_called = []
        monkeypatch.setattr("authsome.cli.advanced.click.confirm", lambda *a, **kw: confirm_called.append(True))

        # Patch requests.head to avoid real network call
        monkeypatch.setattr("authsome.cli.advanced.requests.head", lambda *a, **kw: MagicMock())

        result = runner.invoke(cli, ["--log-file", "", "register", str(path), "--yes"])
        assert result.exit_code == 0, result.output
        assert not confirm_called, "confirm() should not be called with --yes"

    def test_register_calls_client(
        self, runner: CliRunner, mock_client: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = _write_provider(tmp_path, _VALID_API_KEY_PROVIDER)
        monkeypatch.setattr("authsome.cli.advanced.requests.head", lambda *a, **kw: MagicMock())

        runner.invoke(cli, ["--log-file", "", "register", str(path), "--yes"])
        mock_client.register_provider.assert_called_once()
        call_kwargs = mock_client.register_provider.call_args.kwargs
        assert call_kwargs["force"] is False

    def test_force_flag_passed_to_client(
        self, runner: CliRunner, mock_client: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = _write_provider(tmp_path, _VALID_API_KEY_PROVIDER)
        monkeypatch.setattr("authsome.cli.advanced.requests.head", lambda *a, **kw: MagicMock())

        runner.invoke(cli, ["--log-file", "", "register", str(path), "--yes", "--force"])
        call_kwargs = mock_client.register_provider.call_args.kwargs
        assert call_kwargs["force"] is True

    def test_http_endpoint_rejected(self, runner: CliRunner, mock_client: MagicMock, tmp_path: Path) -> None:
        """OAuth providers with http:// token_url should be rejected."""
        bad_provider = {
            **_VALID_OAUTH_PROVIDER,
            "oauth": {
                "authorization_url": "http://insecure.example.com/auth",  # http, not https
                "token_url": "https://example.com/token",
            },
        }
        path = _write_provider(tmp_path, bad_provider)
        result = runner.invoke(cli, ["--log-file", "", "register", str(path), "--yes"])
        assert result.exit_code == 1

    def test_localhost_endpoint_rejected(self, runner: CliRunner, mock_client: MagicMock, tmp_path: Path) -> None:
        """Providers with localhost endpoints should be rejected."""
        bad_provider = {
            **_VALID_OAUTH_PROVIDER,
            "oauth": {
                "authorization_url": "https://localhost/auth",
                "token_url": "https://example.com/token",
            },
        }
        path = _write_provider(tmp_path, bad_provider)
        result = runner.invoke(cli, ["--log-file", "", "register", str(path), "--yes"])
        assert result.exit_code == 1

    def test_json_output_on_success(
        self, runner: CliRunner, mock_client: MagicMock, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = _write_provider(tmp_path, _VALID_API_KEY_PROVIDER)
        monkeypatch.setattr("authsome.cli.advanced.requests.head", lambda *a, **kw: MagicMock())

        result = runner.invoke(cli, ["--log-file", "", "register", str(path), "--yes", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "registered"
        assert data["provider"] == "myprov"
