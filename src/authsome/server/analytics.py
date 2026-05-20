"""PostHog analytics client for the Authsome daemon."""

from __future__ import annotations

import os

from posthog import Posthog

_client: Posthog | None = None


def get_posthog() -> Posthog | None:
    """Return the shared PostHog client, or None if not initialised."""
    return _client


def init_posthog() -> Posthog | None:
    """Initialise the PostHog client from environment variables.

    Returns the client if credentials are present, otherwise None so the
    daemon can run without PostHog configured.
    """
    global _client
    api_key = os.environ.get("POSTHOG_API_KEY", "")
    host = os.environ.get("POSTHOG_HOST", "")
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
