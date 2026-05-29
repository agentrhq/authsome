"""Server-owned audit log export and query support."""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from loguru import logger
from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import (
    BatchLogRecordProcessor,
    LogRecordExporter,
    LogRecordExportResult,
)

from authsome.audit import AuditEvent
from authsome.utils import utc_now


class SQLiteLogExporter(LogRecordExporter):
    """Persist Authsome audit OTel log records into a server-owned SQLite DB."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._closed = False
        self._ensure_schema()

    @property
    def path(self) -> Path:
        return self._path

    def export(self, batch: Sequence[Any]) -> LogRecordExportResult:
        if self._closed:
            return LogRecordExportResult.FAILURE

        rows: list[tuple[str, str, str, str | None, str | None, str | None, str | None, str | None, str]] = []
        for item in batch:
            payload = _payload_from_log_record(item)
            try:
                event = AuditEvent.model_validate(payload)
            except ValueError as exc:
                logger.debug("Skipping non-Authsome OTel log record: {}", exc)
                continue
            normalized = event.model_dump(mode="json")
            stored_payload = _flatten_event_payload(normalized)
            rows.append(
                (
                    event.event_id,
                    normalized["timestamp"],
                    event.event,
                    event.source,
                    event.principal_id,
                    event.identity,
                    event.provider,
                    event.connection,
                    json.dumps(stored_payload, separators=(",", ":"), sort_keys=True),
                )
            )

        if not rows:
            return LogRecordExportResult.SUCCESS

        with self._lock, self._connect() as connection:
            connection.executemany(
                "INSERT OR IGNORE INTO audit_events "
                "(event_id, timestamp, event, source, principal_id, identity, provider, connection, payload_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
        return LogRecordExportResult.SUCCESS

    def shutdown(self) -> None:
        self._closed = True

    def list_events(self, *, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent audit events as JSON-compatible dictionaries."""
        bounded_limit = min(max(limit, 1), 500)
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT payload_json FROM audit_events ORDER BY timestamp DESC, event_id DESC LIMIT ?",
                [bounded_limit],
            ).fetchall()
        return [json.loads(row["payload_json"]) for row in rows]

    def _ensure_schema(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS audit_events ("
                "event_id TEXT PRIMARY KEY, "
                "timestamp TEXT NOT NULL, "
                "event TEXT NOT NULL, "
                "source TEXT NOT NULL, "
                "principal_id TEXT, "
                "identity TEXT, "
                "provider TEXT, "
                "connection TEXT, "
                "payload_json TEXT NOT NULL, "
                "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP"
                ")"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_events_timestamp ON audit_events(timestamp DESC, event_id DESC)"
            )
            connection.execute("CREATE INDEX IF NOT EXISTS idx_audit_events_principal ON audit_events(principal_id)")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        return connection


class _DelegatingLogRecordExporter(LogRecordExporter):
    """Stable global exporter that forwards to the current server exporter."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active: SQLiteLogExporter | None = None

    def set_active(self, exporter: SQLiteLogExporter | None) -> None:
        with self._lock:
            self._active = exporter

    def export(self, batch: Sequence[Any]) -> LogRecordExportResult:
        with self._lock:
            exporter = self._active
        if exporter is None:
            return LogRecordExportResult.SUCCESS
        return exporter.export(batch)

    def shutdown(self) -> None:
        with self._lock:
            exporter = self._active
            self._active = None
        if exporter is not None:
            exporter.shutdown()


_delegating_exporter = _DelegatingLogRecordExporter()
_provider_lock = threading.Lock()
_logger_provider: LoggerProvider | None = None


class ServerAuditLog:
    """Server composition object for emitting and querying audit records."""

    def __init__(self, exporter: SQLiteLogExporter, provider: LoggerProvider) -> None:
        self._exporter = exporter
        self._provider = provider

    @property
    def path(self) -> Path:
        return self._exporter.path

    def force_flush(self) -> None:
        self._provider.force_flush()

    def list_events(self, *, limit: int = 50) -> list[dict[str, Any]]:
        self.force_flush()
        return self._exporter.list_events(limit=limit)

    def shutdown(self) -> None:
        self.force_flush()
        _delegating_exporter.set_active(None)
        self._exporter.shutdown()


def configure_server_audit_log(path: Path) -> ServerAuditLog:
    """Configure the process OTel logger provider to export audit logs to SQLite."""
    global _logger_provider

    exporter = SQLiteLogExporter(path)
    with _provider_lock:
        if _logger_provider is None:
            provider = LoggerProvider()
            provider.add_log_record_processor(BatchLogRecordProcessor(_delegating_exporter))
            try:
                set_logger_provider(provider)
            except Exception as exc:  # pragma: no cover - OTel guards against repeated global setup
                logger.warning("Could not set OpenTelemetry logger provider: {}", exc)
            _logger_provider = provider
        _delegating_exporter.set_active(exporter)
        return ServerAuditLog(exporter, _logger_provider)


def _payload_from_log_record(item: Any) -> dict[str, Any]:
    log_record = getattr(item, "log_record", item)
    attributes = dict(getattr(log_record, "attributes", None) or {})
    if "event" in attributes:
        return attributes

    event_name = getattr(log_record, "event_name", None) or getattr(log_record, "body", "audit_event")
    return AuditEvent(event=str(event_name), timestamp=utc_now()).model_dump(mode="json")


def _flatten_event_payload(payload: dict[str, Any]) -> dict[str, Any]:
    flattened = dict(payload)
    metadata = flattened.pop("metadata", {})
    if isinstance(metadata, dict):
        flattened.update(metadata)
    return flattened
