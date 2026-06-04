"""Daemon CLI commands."""

import sys

import click

from authsome.cli import daemon_control
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
from authsome.server.config import get_server_config
from authsome.server.daemon import serve


@click.group(name="daemon")
def daemon() -> None:
    """Manage the local Authsome daemon."""


@daemon.command(name="serve")
@click.option(
    "--host", default=get_server_config().host, show_default=True, metavar="HOST", help="Host interface to bind."
)
@click.option(
    "--port",
    default=get_server_config().port,
    type=int,
    show_default=True,
    metavar="PORT",
    help="TCP port to listen on.",
)
@click.option("--reload", is_flag=True, help="Enable auto-reload on code changes.")
def daemon_serve(host: str, port: int, reload: bool) -> None:
    """Run the daemon in the foreground."""
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
    log_file = daemon_control.LOG_FILE
    if not log_file.exists():
        ctx_obj.print_json({"log_file": str(log_file), "entries": []})
        return
    entries = log_file.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]
    ctx_obj.print_json({"log_file": str(log_file), "entries": entries})
