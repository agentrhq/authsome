from authsome.server import analytics


def test_init_posthog_respects_disable_flags_and_initialises_when_enabled(monkeypatch) -> None:
    class DummyPosthog:
        def __init__(self, api_key: str, *, host: str, enable_exception_autocapture: bool) -> None:
            self.api_key = api_key
            self.host = host
            self.enable_exception_autocapture = enable_exception_autocapture

        def shutdown(self) -> None:
            return None

    monkeypatch.setattr(analytics, "Posthog", DummyPosthog)

    for env_var_name, disabled_value in (
        ("DO_NOT_TRACK", "1"),
        ("POSTHOG_DISABLED", "1"),
        ("AUTHSOME_ANALYTICS", "0"),
    ):
        monkeypatch.delenv("DO_NOT_TRACK", raising=False)
        monkeypatch.delenv("POSTHOG_DISABLED", raising=False)
        monkeypatch.delenv("AUTHSOME_ANALYTICS", raising=False)
        monkeypatch.setenv(env_var_name, disabled_value)

        analytics.shutdown_posthog()

        assert analytics.init_posthog() is None
        assert analytics.get_posthog() is None

    monkeypatch.delenv("DO_NOT_TRACK", raising=False)
    monkeypatch.delenv("POSTHOG_DISABLED", raising=False)
    monkeypatch.delenv("AUTHSOME_ANALYTICS", raising=False)

    analytics.shutdown_posthog()
    client = analytics.init_posthog()

    assert isinstance(client, DummyPosthog)
    assert client.api_key == "phc_6HXMDi8CjfIW0l04l34L7IDkpCDeOVz9cOz1KLAHXh8"
    assert client.host == "https://us.i.posthog.com"
    assert client.enable_exception_autocapture is True

    analytics.shutdown_posthog()
