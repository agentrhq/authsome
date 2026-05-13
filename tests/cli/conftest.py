"""Shared fixtures for CLI command tests.

All CLI tests operate at the Click boundary: real Click code runs (arg parsing,
decorators, error handling, output formatting) but the daemon client is replaced
by a MagicMock so no network or running daemon is required.

The mock boundary is resolve_runtime_client() in daemon_control — the single
seam between the CLI and the daemon API.
"""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from click.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    """Click test runner."""
    return CliRunner()


@pytest.fixture
def mock_client() -> AsyncMock:
    """Pre-configured mock of AuthsomeApiClient with sane defaults."""
    client = AsyncMock()
    client.base_url = "http://127.0.0.1:7998"

    # Default whoami response
    client.whoami.return_value = {
        "version": "0.0.0",
        "home": "/home/test/.authsome",
        "identity": "steady-wisely-boldly-0042",
        "did": "did:key:z6MkTest",
        "registration_status": "registered",
        "encryption_backend": "local_key",
    }

    # Default doctor/ready response
    client.doctor.return_value = {
        "status": "ready",
        "checks": {"vault": "ok"},
        "issues": [],
    }

    # Default empty connections
    client.list_connections.return_value = {
        "connections": [],
        "by_source": {"bundled": [], "custom": []},
    }

    return client


@pytest.fixture(autouse=True)
def _patch_runtime(mock_client: AsyncMock, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Replace resolve_runtime_client so CLI commands get the mock client.

    Also patch audit.setup and audit.log to prevent real file writes,
    and redirect AUTHSOME_HOME to a temporary directory.
    """
    monkeypatch.setenv("AUTHSOME_HOME", str(tmp_path))

    from unittest import mock

    import authsome.cli.daemon_control as dc

    monkeypatch.setattr(dc, "resolve_runtime_client", mock.AsyncMock(return_value=mock_client))

    import authsome.cli.context as context_mod
    import authsome.cli.main as main_mod

    monkeypatch.setattr(context_mod, "resolve_runtime_client", mock.AsyncMock(return_value=mock_client))
    monkeypatch.setattr(main_mod.audit, "setup", lambda *a, **kw: None)
    monkeypatch.setattr(main_mod.audit, "log", lambda *a, **kw: None)

    import webbrowser

    monkeypatch.setattr(webbrowser, "open", lambda *a, **kw: True)
