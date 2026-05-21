"""Domain model for server-registered identity bindings.

The IdentityRegistry persistence implementation lives in server/registries.py.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class IdentityRegistration(BaseModel):
    """Registered identity binding stored by the daemon."""

    handle: str
    did: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
