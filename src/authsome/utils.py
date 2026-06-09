"""Shared utility functions for authsome."""

import ctypes
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
import typing
from ctypes import wintypes
from datetime import UTC, datetime
from typing import Any

from authsome.auth.models.connection import Sensitive
from authsome.errors import AuthsomeError

SECONDS_PER_MINUTE = 60
MINUTES_PER_HOUR = 60
HOURS_PER_DAY = 24
EXIT_SUCCESS = 0
EXIT_GENERAL_ERROR = 1
EXIT_AUTHENTICATION_FAILED = 2
EXIT_CONNECTION_NOT_FOUND = 3
EXIT_PROVIDER_NOT_FOUND = 4
EXIT_CREDENTIAL_MISSING = 5
EXIT_CONNECTION_ALREADY_EXISTS = 6
EXIT_PROVIDER_ALREADY_REGISTERED = 7
EXIT_ENDPOINT_UNREACHABLE = 8
EXIT_DAEMON_UNAVAILABLE = 9


_JSONC_STRIP_RE = re.compile(r'"(?:[^"\\]|\\.)*"|//[^\n]*|/\*.*?\*/', re.DOTALL)


def parse_jsonc(text: str) -> Any:
    """Parse JSON with C-style comments (JSONC).

    Strips ``//`` line comments and ``/* */`` block comments before passing
    to the standard JSON parser.  String literals are preserved verbatim so
    comment-like sequences inside quoted values are never stripped.
    """

    def _strip(m: re.Match) -> str:
        return m.group(0) if m.group(0).startswith('"') else ""

    return json.loads(_JSONC_STRIP_RE.sub(_strip, text))


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
    total_seconds = max(total_seconds, 0)
    if total_seconds < SECONDS_PER_MINUTE:
        return f"{total_seconds}s"
    minutes = total_seconds // SECONDS_PER_MINUTE
    if minutes < MINUTES_PER_HOUR:
        return f"{minutes}m"
    hours = minutes // MINUTES_PER_HOUR
    if hours < HOURS_PER_DAY:
        return f"{hours}h"
    days = hours // HOURS_PER_DAY
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
    return not (".." in name or "/" in name or "\\" in name)


def redact(record: Any, redacted_value: str = "***REDACTED***") -> dict[str, Any]:
    """
    Return a dict of a Pydantic model with Sensitive-annotated fields replaced.

    Uses get_type_hints(include_extras=True) to detect Annotated[..., Sensitive()]
    fields and replaces their values with redacted_value before display.
    """

    data = record.model_dump(mode="json")
    try:
        hints = typing.get_type_hints(type(record), include_extras=True)
    except Exception:
        return data

    for field_name, hint in hints.items():
        if typing.get_origin(hint) is typing.Annotated:
            metadata = typing.get_args(hint)[1:]
            if any(isinstance(m, Sensitive) for m in metadata) and data.get(field_name) is not None:
                data[field_name] = redacted_value
    return data


def require_os_auth(action_name: str) -> bool:  # noqa: PLR0911
    """
    Prompt the user for OS-level authentication (e.g., Touch ID on macOS)
    before allowing a sensitive action. Returns True if authenticated, False otherwise.
    """
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


def format_error_code(exc: Exception) -> int:  # noqa: PLR0911
    """Return a numerical exit code representing the exception type."""
    if exc.__class__.__name__ == "DaemonUnavailableError":
        return EXIT_DAEMON_UNAVAILABLE
    if not isinstance(exc, AuthsomeError | FileExistsError):
        return EXIT_GENERAL_ERROR
    exc_name = exc.__class__.__name__
    if exc_name in ("AuthenticationFailedError", "InputCancelledError"):
        return EXIT_AUTHENTICATION_FAILED
    if exc_name == "ConnectionNotFoundError":
        return EXIT_CONNECTION_NOT_FOUND
    if exc_name in ("ProviderNotFoundError", "OperationNotAllowedError"):
        return EXIT_PROVIDER_NOT_FOUND
    if exc_name in ("CredentialMissingError", "TokenExpiredError", "RefreshFailedError"):
        return EXIT_CREDENTIAL_MISSING
    if exc_name == "ConnectionAlreadyExistsError":
        return EXIT_CONNECTION_ALREADY_EXISTS
    if exc_name in ("ProviderAlreadyRegisteredError", "FileExistsError"):
        return EXIT_PROVIDER_ALREADY_REGISTERED
    if exc_name == "EndpointUnreachableError":
        return EXIT_ENDPOINT_UNREACHABLE
    return EXIT_GENERAL_ERROR
