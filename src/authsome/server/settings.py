"""Server-owned runtime settings, backed by environment variables.

Deployment knobs (host, port, base URL, token/session lifetimes, analytics)
live here instead of being scattered as module-level constants. Reach for this
over hand-rolled ``os.environ`` lookups.

Invariants that must never vary per deployment — the OAuth callback path, the
session cookie name, the JWT audience, the AES key size — stay as module
constants in their owning modules and are intentionally *not* exposed here.

Per-process secrets (vault master key, UI signing key) keep their dedicated
resolver in ``secrets.py`` so tests can monkeypatch the environment freely.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerSettings(BaseSettings):
    """Daemon runtime settings resolved from ``AUTHSOME_*`` environment variables."""

    model_config = SettingsConfigDict(env_prefix="AUTHSOME_", extra="ignore")

    # ── Network ──────────────────────────────────────────────────────────
    host: str = "127.0.0.1"
    port: int = 7998
    # AUTHSOME_SERVER_BASE_URL; empty falls back to host:port via resolved_base_url.
    server_base_url: str = ""

    # ── Lifetimes (seconds) ──────────────────────────────────────────────
    ui_bootstrap_ttl_seconds: int = 300
    ui_session_ttl_seconds: int = 3600
    token_near_expiry_seconds: int = 300

    # ── Account policy ───────────────────────────────────────────────────
    min_password_length: int = 8

    # ── Analytics ────────────────────────────────────────────────────────
    analytics: bool = True  # AUTHSOME_ANALYTICS=0 disables
    posthog_api_key: str = "YOUR_API_KEY_HERE"
    posthog_host: str = "https://us.i.posthog.com"
    # Industry-standard, non-prefixed opt-out flags.
    do_not_track: bool = Field(default=False, validation_alias=AliasChoices("DO_NOT_TRACK"))
    posthog_disabled: bool = Field(default=False, validation_alias=AliasChoices("POSTHOG_DISABLED"))

    @property
    def resolved_base_url(self) -> str:
        """Canonical external base URL, derived from host/port when unset."""
        return (self.server_base_url or f"http://{self.host}:{self.port}").rstrip("/")

    @property
    def analytics_enabled(self) -> bool:
        """True only when analytics is on and no opt-out flag is set."""
        return self.analytics and not self.do_not_track and not self.posthog_disabled


@lru_cache
def get_settings() -> ServerSettings:
    """Return the process-wide server settings (read once from the environment)."""
    return ServerSettings()
