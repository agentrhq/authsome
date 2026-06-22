"""Tests for `authsome onboard`."""

import json
from pathlib import Path

from authsome import __version__
from authsome.cli.config import ClientConfig
from authsome.cli.identity import RuntimeIdentity
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


class TestOnboardCommand:
    """Behavior tests for onboard setup and credential import."""

    def test_onboard_creates_identity_and_imports_key_from_dotenv(
        self, runner, mock_client, monkeypatch, tmp_path: Path
    ) -> None:
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
        created = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")
        mock_client.ensure_identity_ready.return_value = created
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".env").write_text("BREVO_API_KEY=test123\n", encoding="utf-8")

        result = runner.invoke(cli, ["--log-file", "", "onboard"])

        assert result.exit_code == 0, result.output
        mock_client.ensure_identity_ready.assert_called_once()
        mock_client.whoami.assert_called_once()
        mock_client.start_login.assert_called_once_with(
            provider="brevo", connection="brevo", flow="api_key", force=True
        )
        mock_client.resume_login_session.assert_called_once_with("sess-1", api_key="test123")
        data = json.loads(result.output)
        assert data["status"] == "onboarded"
        assert data["import"] is True
        assert data["imported_count"] == 1

    def test_onboard_removes_legacy_default_state(self, runner, mock_client, tmp_path: Path) -> None:
        identities = tmp_path / "client" / "identities"
        identities.mkdir(parents=True)
        (identities / "default.json").write_text("{}", encoding="utf-8")
        (identities / "default.key").write_text("legacy\n", encoding="utf-8")

        created = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")
        mock_client.ensure_identity_ready.return_value = created

        result = runner.invoke(cli, ["--log-file", "", "onboard", "--scan-only"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["agent"] != "default"
        assert data["registration_status"] == "registered"
        assert not (identities / "default.json").exists()
        assert not (identities / "default.key").exists()
        mock_client.ensure_identity_ready.assert_called_once()

        config_data = ClientConfig.load(tmp_path)
        assert config_data.version == __version__
        assert config_data.active_identity == data["agent"]

    def test_onboard_skips_registration_for_registered_active_agent(self, runner, mock_client, tmp_path: Path) -> None:
        identity = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")
        ClientConfig(active_identity=identity.handle).save(tmp_path)

        result = runner.invoke(cli, ["--log-file", "", "onboard", "--scan-only"])

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["agent"] == identity.handle
        mock_client.ensure_identity_ready.assert_called_once()

    def test_onboard_scan_only_does_not_import(self, runner, mock_client, monkeypatch) -> None:
        mock_client.list_connections.return_value = {
            "connections": [],
            "by_source": {"bundled": [_api_key_provider("openai", "OPENAI_API_KEY")], "custom": []},
        }
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-value")
        mock_client.get_connection.return_value = {}

        result = runner.invoke(cli, ["--log-file", "", "onboard", "--scan-only"])

        assert result.exit_code == 0, result.output
        mock_client.start_login.assert_not_called()
        mock_client.resume_login_session.assert_not_called()
        data = json.loads(result.output)
        assert data["import"] is False

    def test_onboard_rejects_quiet_flag(self, runner, mock_client) -> None:
        result = runner.invoke(cli, ["--log-file", "", "onboard", "--quiet"])
        assert result.exit_code == 1
        data = json.loads(result.output)
        assert data["error"] == "UsageError"
        mock_client.list_connections.assert_not_called()

    def test_onboard_reports_drift_states(self, runner, mock_client, monkeypatch) -> None:
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

        result = runner.invoke(cli, ["--log-file", "", "onboard", "--scan-only"])

        assert result.exit_code == 0, result.output
        payload = json.loads(result.output)
        statuses = {item["provider"]: item["status"] for item in payload["results"]}
        assert statuses["openai"] == "env_and_authsome_different"
        assert statuses["brevo"] == "authsome_only"
        assert statuses["resend"] == "both_missing"

    def test_onboard_persists_base_url_in_client_config(self, runner, mock_client, tmp_path: Path) -> None:
        result = runner.invoke(
            cli,
            ["--log-file", "", "onboard", "--base-url", "https://authsome.example.com", "--scan-only"],
        )

        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["daemon_base_url"] == "https://authsome.example.com"
        assert ClientConfig.load(tmp_path).daemon_base_url == "https://authsome.example.com"
