"""Shared utility functions for authsome."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from authsome.errors import AuthsomeError


def utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(UTC)


def to_rfc3339(dt: datetime) -> str:
    """Format a datetime as RFC 3339 / ISO 8601 in UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat().replace("+00:00", "Z")


def format_duration(total_seconds: int) -> str:
    """Return a compact readable string for a duration in seconds."""
    if total_seconds < 0:
        total_seconds = 0
    if total_seconds < 60:
        return f"{total_seconds}s"
    minutes = total_seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    days = hours // 24
    return f"{days}d"


def parse_rfc3339(s: str) -> datetime:
    """Parse an RFC 3339 datetime string."""
    s = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s)


def is_filesystem_safe(name: str) -> bool:
    """
    Check if a name is safe for use as a filesystem path component.

    Spec §21.1: name must be filesystem-safe.
    """
    if not name:
        return False
    # Allow only alphanumeric, hyphens, underscores, dots (no leading dot)
    if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$", name):
        return False
    # Block path traversal
    if ".." in name or "/" in name or "\\" in name:
        return False
    return True


def redact(record: Any, redacted_value: str = "***REDACTED***") -> dict[str, Any]:
    """
    Return a dict of a Pydantic model with Sensitive-annotated fields replaced.

    Uses get_type_hints(include_extras=True) to detect Annotated[..., Sensitive()]
    fields and replaces their values with redacted_value before display.
    """
    import typing

    from authsome.auth.models.connection import Sensitive

    data = record.model_dump(mode="json")
    try:
        hints = typing.get_type_hints(type(record), include_extras=True)
    except Exception:
        return data

    for field_name, hint in hints.items():
        if typing.get_origin(hint) is typing.Annotated:
            metadata = typing.get_args(hint)[1:]
            if any(isinstance(m, Sensitive) for m in metadata):
                if data.get(field_name) is not None:
                    data[field_name] = redacted_value
    return data


def require_os_auth(action_name: str) -> bool:
    """
    Prompt the user for OS-level authentication (e.g., Touch ID on macOS)
    before allowing a sensitive action. Returns True if authenticated, False otherwise.
    """
    import subprocess
    import sys

    if sys.platform == "darwin":
        prompt = f"Authsome requires authentication to {action_name}."
        script = f'do shell script "echo authenticated" with prompt "{prompt}" with administrator privileges'
        try:
            subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                check=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False
    elif sys.platform.startswith("linux"):
        import shutil

        if shutil.which("pkexec"):
            try:
                subprocess.run(["pkexec", "true"], check=True, capture_output=True)
                return True
            except subprocess.CalledProcessError:
                return False
        elif shutil.which("sudo"):
            print(f"Authsome requires authentication to {action_name}.")
            try:
                subprocess.run(["sudo", "-v"], check=True)
                return True
            except subprocess.CalledProcessError:
                return False
        return False
    elif sys.platform == "win32":
        import ctypes
        import getpass
        import os
        from ctypes import wintypes

        try:
            password = getpass.getpass(f"Authsome requires authentication to {action_name}. Password: ")
            if not password:
                return False

            logon32_logon_interactive = 2
            logon32_provider_default = 0

            token = wintypes.HANDLE()
            username = os.environ.get("USERNAME", "")

            result = ctypes.windll.advapi32.LogonUserW(
                username,
                None,
                password,
                logon32_logon_interactive,
                logon32_provider_default,
                ctypes.byref(token),
            )
            if result:
                ctypes.windll.kernel32.CloseHandle(token)
                return True
            return False
        except (KeyboardInterrupt, EOFError):
            return False

    return False


def format_expires_at(expires_at: str | None) -> str | None:
    """Return a compact relative expiry label for CLI output."""
    if not expires_at:
        return None
    try:
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return f"expires at {expires_at}"
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)

    total_seconds = round((expiry - datetime.now(UTC)).total_seconds())
    if total_seconds < 0:
        label = format_duration(-total_seconds)
        return f"expired {label} ago"
    label = format_duration(total_seconds)
    return f"expires in {label}"


def connection_is_active(connection: dict[str, Any]) -> bool:
    """Return whether a connection should count as actively connected."""
    if connection.get("status") != "connected":
        return False

    expires_at = connection.get("expires_at")
    if not expires_at:
        return True
    try:
        expiry = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
    except ValueError:
        return True
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    return datetime.now(UTC) < expiry


def format_error_code(exc: Exception) -> int:
    """Return a numerical exit code representing the exception type."""
    if exc.__class__.__name__ == "DaemonUnavailableError":
        return 9
    if not isinstance(exc, AuthsomeError | FileExistsError):
        return 1
    exc_name = exc.__class__.__name__
    if exc_name in ("AuthenticationFailedError", "InputCancelledError"):
        return 2
    if exc_name == "ConnectionNotFoundError":
        return 3
    if exc_name in ("ProviderNotFoundError", "OperationNotAllowedError"):
        return 4
    if exc_name in ("CredentialMissingError", "TokenExpiredError", "RefreshFailedError"):
        return 5
    if exc_name == "ConnectionAlreadyExistsError":
        return 6
    if exc_name in ("ProviderAlreadyRegisteredError", "FileExistsError"):
        return 7
    if exc_name == "EndpointUnreachableError":
        return 8
    return 1
