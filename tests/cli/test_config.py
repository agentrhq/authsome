"""Tests for `authsome config get` and `authsome config set`."""

import json

import pytest

from authsome.cli.main import cli


class TestConfigGet:
    """Tests for `authsome config get proxy-mode`."""

    def test_get_returns_default_mode(self, runner) -> None:
        result = runner.invoke(cli, ["--log-file", "", "config", "get", "proxy-mode"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["proxy_mode"] == "connected_allow"

    def test_get_reflects_saved_mode(self, runner, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
        from authsome.cli.client_config import ClientConfig, save_client_config

        save_client_config(tmp_path, ClientConfig(proxy_mode="configured_deny"))

        result = runner.invoke(cli, ["--log-file", "", "config", "get", "proxy-mode"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["proxy_mode"] == "configured_deny"

    def test_get_unknown_key_returns_error(self, runner) -> None:
        result = runner.invoke(cli, ["--log-file", "", "config", "get", "unknown-key"])
        assert result.exit_code != 0
        data = json.loads(result.output)
        assert data["error"] == "UnknownConfigKey"
        assert "proxy-mode" in data["message"]


class TestConfigSet:
    """Tests for `authsome config set proxy-mode <value>`."""

    @pytest.mark.parametrize(
        "mode",
        ["connected_allow", "connected_deny", "configured_allow", "configured_deny"],
    )
    def test_set_all_valid_modes(self, runner, tmp_path, monkeypatch, mode) -> None:
        monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

        result = runner.invoke(cli, ["--log-file", "", "config", "set", "proxy-mode", mode])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        assert data["status"] == "ok"
        assert data["proxy_mode"] == mode

    def test_set_persists_to_disk(self, runner, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))
        from authsome.cli.client_config import load_client_config

        runner.invoke(cli, ["--log-file", "", "config", "set", "proxy-mode", "connected_deny"])
        assert load_client_config(tmp_path).proxy_mode == "connected_deny"

    def test_set_invalid_mode_returns_error(self, runner) -> None:
        result = runner.invoke(cli, ["--log-file", "", "config", "set", "proxy-mode", "bad_value"])
        assert result.exit_code != 0
        data = json.loads(result.output)
        assert data["error"] == "InvalidProxyMode"
        assert "bad_value" in data["message"]
        for valid in ("connected_allow", "connected_deny", "configured_allow", "configured_deny"):
            assert valid in data["message"]

    def test_set_unknown_key_returns_error(self, runner) -> None:
        result = runner.invoke(cli, ["--log-file", "", "config", "set", "unknown-key", "value"])
        assert result.exit_code != 0
        data = json.loads(result.output)
        assert data["error"] == "UnknownConfigKey"
        assert "proxy-mode" in data["message"]
