"""Tests for `authsome scan`."""

import json

from authsome.cli.main import cli


def _api_key_provider(name: str, env_var: str) -> dict:
    return {
        "schema_version": 1,
        "name": name,
        "display_name": name.title(),
        "auth_type": "api_key",
        "flow": "api_key",
        "api_key": {"header_name": "Authorization", "header_prefix": "Bearer"},
        "export": {"env": {"api_key": env_var}},
    }


def _oauth_provider(name: str) -> dict:
    return {
        "schema_version": 1,
        "name": name,
        "display_name": name.title(),
        "auth_type": "oauth2",
        "flow": "pkce",
        "oauth": {"authorization_url": "https://example.com/auth", "token_url": "https://example.com/token"},
    }


class TestScanCommand:
    """Behavior tests for scan and import workflow."""

    def test_scan_import_flag_imports_key_from_dotenv(self, runner, mock_client, monkeypatch, tmp_path) -> None:
        mock_client.list_connections.return_value = {
            "connections": [],
            "by_source": {
                "bundled": [_api_key_provider("brevo", "BREVO_API_KEY"), _oauth_provider("github")],
                "custom": [],
            },
        }
        mock_client.get_connection.side_effect = Exception("not found")
        mock_client.start_login.return_value = {"id": "sess-1", "status": "pending"}
        mock_client.resume_login_session.return_value = {"id": "sess-1", "status": "completed"}
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text("BREVO_API_KEY=test123\n", encoding="utf-8")

        result = runner.invoke(cli, ["--log-file", "", "scan", "--import"])

        assert result.exit_code == 0, result.output
        mock_client.start_login.assert_called_once_with(
            provider="brevo", connection="default", flow="api_key", force=True
        )
        mock_client.resume_login_session.assert_called_once_with("sess-1", api_key="test123")
        data = json.loads(result.output)
        assert data["import"] is True

    def test_scan_defaults_to_report_only(self, runner, mock_client, monkeypatch) -> None:
        mock_client.list_connections.return_value = {
            "connections": [],
            "by_source": {"bundled": [_api_key_provider("openai", "OPENAI_API_KEY")], "custom": []},
        }
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-value")
        mock_client.get_connection.return_value = {}

        result = runner.invoke(cli, ["--log-file", "", "scan"])

        assert result.exit_code == 0, result.output
        mock_client.start_login.assert_not_called()
        mock_client.resume_login_session.assert_not_called()
        data = json.loads(result.output)
        assert data["import"] is False

    def test_scan_rejects_quiet_flag(self, runner, mock_client) -> None:
        result = runner.invoke(cli, ["--log-file", "", "scan", "--quiet"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["error"] == "UsageError"
        mock_client.list_connections.assert_not_called()

    def test_scan_reports_drift_states(self, runner, mock_client, monkeypatch) -> None:
        mock_client.list_connections.return_value = {
            "connections": [],
            "by_source": {
                "bundled": [
                    _api_key_provider("openai", "OPENAI_API_KEY"),
                    _api_key_provider("brevo", "BREVO_API_KEY"),
                    _api_key_provider("resend", "RESEND_API_KEY"),
                ],
                "custom": [],
            },
        }
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-1")
        monkeypatch.delenv("BREVO_API_KEY", raising=False)
        monkeypatch.delenv("RESEND_API_KEY", raising=False)

        def _get_connection(provider: str, connection: str):
            if provider == "openai":
                return {"status": "connected", "api_key": "sk-other"}
            if provider == "brevo":
                return {"status": "connected", "api_key": "brevo-live"}
            raise Exception("not found")

        mock_client.get_connection.side_effect = _get_connection

        result = runner.invoke(cli, ["--log-file", "", "scan"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        statuses = {item["provider"]: item["status"] for item in payload["results"]}
        assert statuses["openai"] == "env_and_authsome_different"
        assert statuses["brevo"] == "authsome_only"
        assert statuses["resend"] == "both_missing"
