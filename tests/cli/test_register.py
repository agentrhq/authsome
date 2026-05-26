"""Tests for `authsome provider register`."""

import json
from pathlib import Path
from unittest.mock import MagicMock

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
    """Tests for `authsome provider register <path>`."""

    def test_file_not_found_exits_1(self, runner, mock_client) -> None:
        result = runner.invoke(cli, ["--log-file", "", "provider", "register", "/no/such/file.json", "--yes"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["error"] == "FileNotFoundError"

    def test_invalid_json_exits_1(self, runner, mock_client, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("this is not json", encoding="utf-8")
        result = runner.invoke(cli, ["--log-file", "", "provider", "register", str(bad), "--yes"])
        assert result.exit_code == 1

    def test_register_calls_client(self, runner, mock_client, tmp_path: Path, monkeypatch) -> None:
        path = _write_provider(tmp_path, _VALID_API_KEY_PROVIDER)
        monkeypatch.setattr("authsome.cli.main.requests.head", lambda *a, **kw: MagicMock())

        result = runner.invoke(cli, ["--log-file", "", "provider", "register", str(path), "--yes"])
        assert result.exit_code == 0, result.output
        mock_client.register_provider.assert_called_once()
        call_kwargs = mock_client.register_provider.call_args.kwargs
        assert call_kwargs["force"] is False
        data = json.loads(result.output)
        assert data["status"] == "registered"
        assert data["provider"] == "myprov"

    def test_force_flag_passed_to_client(self, runner, mock_client, tmp_path: Path, monkeypatch) -> None:
        path = _write_provider(tmp_path, _VALID_API_KEY_PROVIDER)
        monkeypatch.setattr("authsome.cli.main.requests.head", lambda *a, **kw: MagicMock())

        runner.invoke(cli, ["--log-file", "", "provider", "register", str(path), "--yes", "--force"])
        call_kwargs = mock_client.register_provider.call_args.kwargs
        assert call_kwargs["force"] is True

    def test_http_endpoint_rejected(self, runner, mock_client, tmp_path: Path) -> None:
        bad_provider = {
            **_VALID_OAUTH_PROVIDER,
            "oauth": {
                "authorization_url": "http://insecure.example.com/auth",
                "token_url": "https://example.com/token",
            },
        }
        path = _write_provider(tmp_path, bad_provider)
        result = runner.invoke(cli, ["--log-file", "", "provider", "register", str(path), "--yes"])
        assert result.exit_code == 1

    def test_localhost_endpoint_rejected(self, runner, mock_client, tmp_path: Path) -> None:
        bad_provider = {
            **_VALID_OAUTH_PROVIDER,
            "oauth": {
                "authorization_url": "https://localhost/auth",
                "token_url": "https://example.com/token",
            },
        }
        path = _write_provider(tmp_path, bad_provider)
        result = runner.invoke(cli, ["--log-file", "", "provider", "register", str(path), "--yes"])
        assert result.exit_code == 1
