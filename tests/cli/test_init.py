"""Tests for `authsome init`."""

import json
from pathlib import Path

from authsome import __version__
from authsome.cli.config import ClientConfig
from authsome.cli.identity import RuntimeIdentity
from authsome.cli.main import cli


def test_init_removes_legacy_default_state_and_registers_identity(
    runner,
    mock_client,
    tmp_path: Path,
) -> None:
    identities = tmp_path / "client" / "identities"
    identities.mkdir(parents=True)
    (identities / "default.json").write_text("{}", encoding="utf-8")
    (identities / "default.key").write_text("legacy\n", encoding="utf-8")

    created = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")
    mock_client.ensure_identity_ready.return_value = created

    result = runner.invoke(cli, ["--log-file", "", "init"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["agent"] != "default"
    assert "profile" not in data
    assert data["registration_status"] == "registered"
    assert data["configured_encryption_mode"] == "auto"
    assert data["effective_encryption_source"] == "local_key"
    assert data["encryption_backend"] == "Local File (/home/test/.authsome/server/master.key)"
    assert not (identities / "default.json").exists()
    assert not (identities / "default.key").exists()
    mock_client.ensure_identity_ready.assert_called_once()
    mock_client.whoami.assert_called_once()

    config_data = ClientConfig.load(tmp_path)
    assert config_data.version == __version__
    assert config_data.active_identity == data["agent"]


def test_init_skips_registration_for_registered_active_agent(
    runner,
    mock_client,
    tmp_path: Path,
) -> None:
    identity = RuntimeIdentity.create(tmp_path, "steady-wisely-boldly-0042")
    ClientConfig(active_identity=identity.handle).save(tmp_path)

    result = runner.invoke(cli, ["--log-file", "", "init"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["agent"] == identity.handle
    assert "profile" not in data
    assert data["configured_encryption_mode"] == "auto"
    mock_client.ensure_identity_ready.assert_called_once()
