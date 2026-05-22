"""PostHog analytics client for the Authsome daemon."""

from __future__ import annotations

import os
from typing import Any

from loguru import logger
from posthog import Posthog

_client: Posthog | None = None
_DISABLE_FLAGS: tuple[tuple[str, str], ...] = (
    ("DO_NOT_TRACK", "1"),
    ("POSTHOG_DISABLED", "1"),
    ("AUTHSOME_ANALYTICS", "0"),
)


def get_posthog() -> Posthog | None:
    """Return the shared PostHog client, or None if not initialised."""
    return _client


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

    for env_var_name, disabled_value in _DISABLE_FLAGS:
        if os.getenv(env_var_name) == disabled_value:
            _client = None
            logger.debug("Analytics disabled via {}", env_var_name)
            return None

    api_key = "phc_6HXMDi8CjfIW0l04l34L7IDkpCDeOVz9cOz1KLAHXh8"
    host = "https://us.i.posthog.com"
    if not api_key or not host:
        return None
    _client = Posthog(api_key, host=host, enable_exception_autocapture=True)
    return _client


def shutdown_posthog() -> None:
    """Flush pending events and shut down the PostHog client."""
    global _client
    if _client is not None:
        _client.shutdown()
        _client = None
