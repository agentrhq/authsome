"""PostHog analytics client for the Authsome daemon."""

from __future__ import annotations

from typing import Any

from loguru import logger
from posthog import Posthog

from authsome.server.settings import get_settings

_client: Posthog | None = None


def capture_event(identity: str, event: str, properties: dict[str, Any]) -> None:
    """Capture a PostHog event. No-op when PostHog is not initialised."""
    ph = _client
    if ph is None:
        return
    from posthog import identify_context, new_context

    with new_context():
        identify_context(identity)
        ph.capture(event, distinct_id=identity, properties=properties)


def init_posthog() -> Posthog | None:
    """Initialise the shared PostHog client unless telemetry is disabled.

    Returns the client when analytics is enabled, otherwise None so the daemon
    can run without emitting telemetry.
    """
    global _client

    settings = get_settings()
    if not settings.analytics_enabled:
        _client = None
        logger.debug("Analytics disabled via settings")
        return None

    _client = Posthog(settings.posthog_api_key, host=settings.posthog_host, enable_exception_autocapture=True)
    return _client


def shutdown_posthog() -> None:
    """Flush pending events and shut down the PostHog client."""
    global _client
    if _client is not None:
        _client.shutdown()
        _client = None
