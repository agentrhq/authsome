"""Local daemon process control for CLI commands."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from authsome.cli.client import (
    DEFAULT_DAEMON_URL,
    AuthsomeApiClient,
    is_managed_local_daemon_url,
    resolve_daemon_url,
)
from authsome.server.daemon import DEFAULT_HOST, DEFAULT_PORT

AUTHSOME_HOME = Path(os.environ.get("AUTHSOME_HOME", str(Path.home() / ".authsome")))
DAEMON_DIR = AUTHSOME_HOME / "server" / "daemon"
PID_FILE = DAEMON_DIR / "daemon.pid"
LOG_FILE = DAEMON_DIR / "daemon.log"
STATE_FILE = DAEMON_DIR / "daemon.json"


class DaemonUnavailableError(RuntimeError):
    """Raised when the local daemon cannot be started or reached."""


async def ensure_daemon() -> AuthsomeApiClient:
    """Return a ready daemon client, starting/restarting the daemon if needed."""
    client = AuthsomeApiClient(DEFAULT_DAEMON_URL)
    if await _is_ready(client):
        return client
    await stop_daemon()
    start_daemon()

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if await _is_ready(client):
            return client
        await asyncio.sleep(0.2)
    raise DaemonUnavailableError(_startup_error())


async def resolve_runtime_client() -> AuthsomeApiClient:
    """Return the configured runtime client, auto-starting only for local mode."""
    client = AuthsomeApiClient(resolve_daemon_url())
    if is_managed_local_daemon_url(client.base_url):
        return await ensure_daemon()
    return client


def start_daemon() -> None:
    # 1. If our tracked lockfile currently points to a running process, do not disrupt it.
    if _pid_file_process_alive():
        return

    DAEMON_DIR.mkdir(parents=True, exist_ok=True)
    log = LOG_FILE.open("ab")
    process = subprocess.Popen(
        [sys.executable, "-m", "authsome.cli.main", "daemon", "serve"],
        stdout=log,
        stderr=log,
        start_new_session=True,
    )
    PID_FILE.write_text(str(process.pid), encoding="utf-8")
    STATE_FILE.write_text(
        json.dumps({"pid": process.pid, "host": DEFAULT_HOST, "port": DEFAULT_PORT}, indent=2),
        encoding="utf-8",
    )


async def stop_daemon() -> None:
    pid = _read_pid()
    if pid is None:
        # We do not have a local management record for a daemon.
        # Refuse to blind-kill arbitrary OS processes.
        return

    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        _clear_daemon_files()
        return

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if not _process_alive(pid):
            _clear_daemon_files()
            return
        await asyncio.sleep(0.2)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    _clear_daemon_files()


async def daemon_status() -> dict[str, Any]:
    client = AuthsomeApiClient(DEFAULT_DAEMON_URL)
    try:
        health = await client.health()
        ready = await client.ready()
        return {"running": True, "health": health, "ready": ready, "pid_file": str(PID_FILE), "log_file": str(LOG_FILE)}
    except Exception as exc:
        return {"running": False, "error": str(exc), "pid_file": str(PID_FILE), "log_file": str(LOG_FILE)}


async def _is_ready(client: AuthsomeApiClient) -> bool:
    try:
        health = await client.health()
        from authsome import __version__

        if health.get("version") != __version__:
            return False

        if health.get("status") != "ok":
            return False
        await client.ready()
        return True
    except Exception:
        return False


def _read_pid() -> int | None:
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _pid_file_process_alive() -> bool:
    pid = _read_pid()
    return pid is not None and _process_alive(pid)


def _clear_daemon_files() -> None:
    for path in (PID_FILE, STATE_FILE):
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _startup_error() -> str:
    lines: list[str] = []
    if LOG_FILE.exists():
        lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-12:]
    detail = "\n".join(lines) if lines else "No daemon log output was captured."
    return f"Authsome daemon failed to start.\nLog: {LOG_FILE}\n\n{detail}"
