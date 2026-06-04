"""Tests for pure-logic helper functions in cli/main.py.

These functions have no I/O and require no mocking — they are tested
directly to ensure the formatting, duration, and error-code logic is correct.
"""

# ruff: noqa: PLR2004

from datetime import UTC, datetime, timedelta

import pytest

from authsome.cli.daemon_control import DaemonUnavailableError
from authsome.errors import (
    AuthenticationFailedError,
    ConnectionAlreadyExistsError,
    ConnectionNotFoundError,
    CredentialMissingError,
    EndpointUnreachableError,
    OperationNotAllowedError,
    ProviderAlreadyRegisteredError,
    ProviderNotFoundError,
    RefreshFailedError,
    StoreUnavailableError,
)
from authsome.utils import (
    connection_is_active,
    format_duration,
    format_error_code,
    format_expires_at,
)

# ── format_expires_at ────────────────────────────────────────────────────────


def test_format_expires_at_none_returns_none() -> None:
    assert format_expires_at(None) is None


def test_format_expires_at_future_seconds() -> None:
    future = (datetime.now(UTC) + timedelta(seconds=30)).isoformat()
    label = format_expires_at(future)
    assert label is not None
    assert "expires in" in label
    assert "s" in label


def test_format_expires_at_future_minutes() -> None:
    future = (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
    label = format_expires_at(future)
    assert label is not None
    assert "10m" in label


def test_format_expires_at_future_hours() -> None:
    future = (datetime.now(UTC) + timedelta(hours=5)).isoformat()
    label = format_expires_at(future)
    assert label is not None
    assert "5h" in label


def test_format_expires_at_future_days() -> None:
    future = (datetime.now(UTC) + timedelta(days=3)).isoformat()
    label = format_expires_at(future)
    assert label is not None
    assert "3d" in label


def test_format_expires_at_past() -> None:
    past = (datetime.now(UTC) - timedelta(hours=2)).isoformat()
    label = format_expires_at(past)
    assert label is not None
    assert "expired" in label
    assert "ago" in label


def test_format_expires_at_invalid_string() -> None:
    # Unparseable strings fall back to raw display
    label = format_expires_at("not-a-date")
    assert label is not None
    assert "not-a-date" in label


def test_format_expires_at_z_suffix() -> None:
    """ISO format with Z suffix should be parsed correctly."""
    future = (datetime.now(UTC) + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    label = format_expires_at(future)
    assert label is not None
    assert "expires in" in label


# ── format_duration ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "seconds, expected",
    [
        (0, "0s"),
        (59, "59s"),
        (60, "1m"),
        (90, "1m"),
        (3600, "1h"),
        (7200, "2h"),
        (172800, "2d"),  # 48h exactly → 2d
        (86400, "1d"),
    ],
)
def test_format_duration(seconds: int, expected: str) -> None:
    assert format_duration(seconds) == expected


# ── connection_is_active ─────────────────────────────────────────────────────


def test_connection_is_active_connected_no_expiry() -> None:
    conn = {"status": "connected"}
    assert connection_is_active(conn) is True


def test_connection_is_active_not_connected() -> None:
    conn = {"status": "not_connected"}
    assert connection_is_active(conn) is False


def test_connection_is_active_expired_status() -> None:
    conn = {"status": "expired"}
    assert connection_is_active(conn) is False


def test_connection_is_active_future_expiry() -> None:
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    conn = {"status": "connected", "expires_at": future}
    assert connection_is_active(conn) is True


def test_connection_is_active_past_expiry() -> None:
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    conn = {"status": "connected", "expires_at": past}
    assert connection_is_active(conn) is False


def test_connection_is_active_invalid_expiry_treated_as_active() -> None:
    # Unparseable expiry → assume active (don't break on weird data)
    conn = {"status": "connected", "expires_at": "not-a-date"}
    assert connection_is_active(conn) is True


# ── format_error_code ────────────────────────────────────────────────────────


def test_format_error_code_generic_exception() -> None:
    assert format_error_code(ValueError("oops")) == 1


def test_format_error_code_daemon_unavailable() -> None:
    assert format_error_code(DaemonUnavailableError("down")) == 9


def test_format_error_code_provider_not_found() -> None:
    assert format_error_code(ProviderNotFoundError("x")) == 4


def test_format_error_code_operation_not_allowed() -> None:
    assert format_error_code(OperationNotAllowedError("revoke", "blocked", provider="x")) == 4


def test_format_error_code_authentication_failed() -> None:
    assert format_error_code(AuthenticationFailedError("bad", provider="x")) == 2


def test_format_error_code_credential_missing() -> None:
    assert format_error_code(CredentialMissingError("none", provider="x")) == 5


def test_format_error_code_refresh_failed() -> None:
    assert format_error_code(RefreshFailedError("fail", provider="x")) == 5


def test_format_error_code_store_unavailable() -> None:
    # StoreUnavailableError is now classified as generic (last resort)
    assert format_error_code(StoreUnavailableError("disk")) == 1


def test_format_error_code_connection_not_found() -> None:
    assert format_error_code(ConnectionNotFoundError(provider="x")) == 3


def test_format_error_code_connection_already_exists() -> None:
    assert format_error_code(ConnectionAlreadyExistsError(provider="x")) == 6


def test_format_error_code_provider_already_registered() -> None:
    assert format_error_code(ProviderAlreadyRegisteredError(name="x")) == 7
    assert format_error_code(FileExistsError("oops")) == 7


def test_format_error_code_endpoint_unreachable() -> None:
    assert format_error_code(EndpointUnreachableError(endpoint="x")) == 8


def test_format_error_code_unknown_authsome_error() -> None:
    from authsome.errors import AuthsomeError

    err = AuthsomeError("generic")
    assert format_error_code(err) == 1
