"""Structured audit event emission.

The audit package is intentionally storage-free. It turns Authsome audit
events into OpenTelemetry log records and leaves export decisions to the
server composition root.
"""

import uuid
from datetime import datetime
from typing import Any, Literal

from opentelemetry._logs import SeverityNumber, get_logger
from pydantic import BaseModel, Field

from authsome.utils import utc_now

AuditSource = Literal["internal", "external"]


class AuditEvent(BaseModel):
    """Structured audit event record emitted through OpenTelemetry logs."""

    event_id: str = Field(default_factory=lambda: f"audit_{uuid.uuid4().hex}")
    timestamp: datetime = Field(default_factory=utc_now)
    event: str
    source: AuditSource = "internal"
    provider: str | None = None
    connection: str | None = None
    identity: str | None = None
    principal_id: str | None = None
    status: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


def emit(event: AuditEvent) -> AuditEvent:
    """Emit an audit event through the globally registered OTel logger."""
    logger = get_logger("authsome.audit")
    logger.emit(
        timestamp=int(event.timestamp.timestamp() * 1_000_000_000),
        severity_number=SeverityNumber.INFO,
        severity_text="INFO",
        body=event.event,
        attributes=event.model_dump(mode="json"),
        event_name=event.event,
    )
    return event


def emit_event(  # noqa: PLR0913
    event: str,
    *,
    source: AuditSource = "internal",
    identity: str | None = None,
    principal_id: str | None = None,
    provider: str | None = None,
    connection: str | None = None,
    status: str | None = None,
    **metadata: Any,
) -> AuditEvent:
    """Build and emit a structured audit event."""
    return emit(
        AuditEvent(
            event=event,
            source=source,
            identity=identity,
            principal_id=principal_id,
            provider=provider,
            connection=connection,
            status=status,
            metadata={key: value for key, value in metadata.items() if value is not None},
        )
    )
