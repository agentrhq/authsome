"""Global pytest configuration and early initialization."""

import os
import tempfile

import pytest

# Force a safe temporary AUTHSOME_HOME before any codebase imports occur
_tmp_dir = tempfile.TemporaryDirectory(prefix="authsome_test_home_")
os.environ["AUTHSOME_HOME"] = _tmp_dir.name
os.environ["AUTHSOME_DO_NOT_TRACK"] = "true"
os.environ.pop("AUTHSOME_POSTHOG_API_KEY", None)
os.environ.pop("POSTHOG_API_KEY", None)


@pytest.fixture(autouse=True)
def _disable_analytics(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests must never initialize analytics clients or send telemetry."""
    from authsome.server import analytics
    from authsome.server.config import get_server_config

    get_server_config.cache_clear()
    monkeypatch.setenv("AUTHSOME_DO_NOT_TRACK", "true")
    monkeypatch.delenv("AUTHSOME_POSTHOG_API_KEY", raising=False)
    monkeypatch.delenv("POSTHOG_API_KEY", raising=False)
    analytics.shutdown_posthog()

    class AnalyticsForbidden:
        def __init__(self, *args, **kwargs) -> None:
            raise AssertionError("Tests must not initialize analytics clients")

    monkeypatch.setattr(analytics, "Posthog", AnalyticsForbidden)
