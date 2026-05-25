"""Structured server-side event logging helpers."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from authsome.utils import utc_now


class AuditEvent(BaseModel):
    """Structured server-side event record."""

    event_id: str = Field(default_factory=lambda: f"audit_{uuid.uuid4().hex}")
    timestamp: datetime = Field(default_factory=utc_now)
    event: str
    provider: str | None = None
    connection: str | None = None
    identity: str | None = None
    status: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


_log_path: Path | None = None
_lock = threading.Lock()


def _build_event(event_type: str, **kwargs: Any) -> AuditEvent:
    filtered_kwargs = {k: v for k, v in kwargs.items() if v is not None}
    return AuditEvent(
        event=event_type,
        provider=filtered_kwargs.pop("provider", None),
        connection=filtered_kwargs.pop("connection", None),
        identity=filtered_kwargs.pop("identity", None),
        status=filtered_kwargs.pop("status", None),
        metadata=filtered_kwargs,
    )


def setup(path: Path) -> None:
    """Configure the server-side structured log path."""
    global _log_path
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()
    _log_path = path


def clear() -> None:
    """Clear configured server-side log state."""
    global _log_path
    _log_path = None


def _serialize_event(event: AuditEvent) -> str:
    payload = event.model_dump(mode="json")
    metadata = payload.pop("metadata", {})
    if isinstance(metadata, dict):
        payload.update(metadata)
    return json.dumps(payload, separators=(",", ":"))


# TODO: Better to use an audit library: otel or something similar
def log(event_type: str, **kwargs: Any) -> None:
    """Append a structured server event to the configured log file."""
    if _log_path is None:
        return
    line = _serialize_event(_build_event(event_type, **kwargs))
    with _lock:
        _log_path.parent.mkdir(parents=True, exist_ok=True)
        with _log_path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.write("\n")


# FIXME: Why is there a  log and alog ?
async def alog(event_type: str, **kwargs: Any) -> None:
    """Async wrapper around structured server event logging."""
    log(event_type, **kwargs)
