"""Administrative CLI commands for authsome."""

import json as json_lib
import os
import sys
from pathlib import Path

import click

from authsome.cli.client import resolve_daemon_url
from authsome.cli.context import ContextObj
from authsome.cli.daemon_control import (
    DaemonAlreadyRunningError,
    DaemonUnavailableError,
    daemon_status,
    is_daemon_responsive,
    is_port_occupied,
    start_daemon,
    stop_daemon,
    wait_for_daemon_ready,
)
from authsome.cli.helpers import auth_command
from authsome.paths import get_client_log_path, get_server_log_path


@click.group(name="admin")
def admin() -> None:
    """Manage operator-facing daemon and maintenance commands."""


@admin.command(name="log")
@click.option("-n", "--lines", default=50, metavar="COUNT", help="Number of entries to show.")
@click.option("--raw", is_flag=True, help="Show raw client debug log instead of structured audit entries.")
@auth_command
async def log_cmd(ctx_obj: ContextObj, lines: int, raw: bool) -> None:
    """View structured audit entries or the raw client debug log."""
    home = Path(os.environ.get("AUTHSOME_HOME", str(Path.home() / ".authsome")))

    if raw:
        log_path = get_client_log_path(home)
        try:
            raw_lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
        except FileNotFoundError:
            raw_lines = []
        ctx_obj.print_json({"log_file": str(log_path), "entries": raw_lines})
        return

    audit_path = get_server_log_path(home)
    try:
        raw_lines = audit_path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    except FileNotFoundError:
        raw_lines = []

    parsed: list[dict] = []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            parsed.append(json_lib.loads(line))
        except Exception:
            parsed.append({"raw": line})

    ctx_obj.print_json({"log_file": str(audit_path), "entries": parsed})


@admin.group(name="daemon")
def daemon() -> None:
    """Manage the local Authsome daemon."""


@daemon.command(name="serve")
@click.option("--host", default="127.0.0.1", show_default=True, metavar="HOST", help="Host interface to bind.")
@click.option("--port", default=7998, type=int, show_default=True, metavar="PORT", help="TCP port to listen on.")
@click.option("--reload", is_flag=True, help="Enable auto-reload on code changes.")
def daemon_serve(host: str, port: int, reload: bool) -> None:
    """Run the daemon in the foreground."""
    from authsome.server.daemon import serve

    serve(host=host, port=port, reload=reload)


@daemon.command(name="start")
@auth_command
async def daemon_start(ctx_obj: ContextObj) -> None:
    """Start the local daemon in the background."""
    if await is_daemon_responsive():
        ctx_obj.print_json({"status": "already_running", "message": "Daemon is already running."})
        return

    if is_port_occupied():
        daemon_url = resolve_daemon_url()
        ctx_obj.print_json(
            {
                "status": "port_occupied",
                "message": f"{daemon_url} port is occupied by an unrelated process. We did not start a new process.",
            }
        )
        return

    try:
        start_daemon()
        await wait_for_daemon_ready(timeout=5)
        ctx_obj.print_json({"status": "started", "message": "Daemon started successfully."})
    except DaemonAlreadyRunningError as exc:
        pid_str = f" (PID: {exc.pid})" if exc.pid else ""
        ctx_obj.print_json({"status": "already_running", "message": f"Daemon is already running{pid_str}."})
    except DaemonUnavailableError as exc:
        ctx_obj.print_json({"error": exc.__class__.__name__, "message": str(exc)})
        sys.exit(1)


@daemon.command(name="stop")
@auth_command
async def daemon_stop(ctx_obj: ContextObj) -> None:
    """Stop the local daemon."""
    stopped, message = await stop_daemon()
    status = "stopped" if stopped else "not_stopped"
    ctx_obj.print_json({"status": status, "message": message})


@daemon.command(name="restart")
@auth_command
async def daemon_restart(ctx_obj: ContextObj) -> None:
    """Restart the local daemon."""
    stopped, message = await stop_daemon()

    if await is_daemon_responsive():
        ctx_obj.print_json(
            {
                "status": "already_running",
                "message": "Daemon is already running. We did not start a new process.",
                "stop_message": message,
                "stopped": stopped,
            }
        )
        return

    if is_port_occupied():
        daemon_url = resolve_daemon_url()
        ctx_obj.print_json(
            {
                "status": "port_occupied",
                "message": f"{daemon_url} port is occupied by an unrelated process. We did not start a new process.",
                "stop_message": message,
                "stopped": stopped,
            }
        )
        return

    try:
        start_daemon()
        await wait_for_daemon_ready(timeout=5)
        ctx_obj.print_json(
            {
                "status": "restarted" if stopped else "started",
                "message": "Daemon restarted successfully." if stopped else "New daemon started.",
                "stop_message": message,
                "stopped": stopped,
            }
        )
    except DaemonAlreadyRunningError as exc:
        pid_str = f" (PID: {exc.pid})" if exc.pid else ""
        ctx_obj.print_json(
            {
                "status": "already_running",
                "message": f"Daemon is already running{pid_str}.",
                "stop_message": message,
                "stopped": stopped,
            }
        )
    except DaemonUnavailableError as exc:
        ctx_obj.print_json({"error": exc.__class__.__name__, "message": str(exc)})
        sys.exit(1)


@daemon.command(name="status")
@auth_command
async def daemon_status_cmd(ctx_obj: ContextObj) -> None:
    """Show daemon status."""
    status = await daemon_status()
    ctx_obj.print_json(status)


@daemon.command(name="logs")
@click.option("-n", "--lines", default=80, metavar="COUNT", help="Number of lines to show.")
@auth_command
async def daemon_logs(ctx_obj: ContextObj, lines: int) -> None:
    """Show daemon log output."""
    from authsome.cli.daemon_control import LOG_FILE

    if not LOG_FILE.exists():
        ctx_obj.print_json({"log_file": str(LOG_FILE), "entries": []})
        return
    entries = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    ctx_obj.print_json({"log_file": str(LOG_FILE), "entries": entries})
