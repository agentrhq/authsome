"""Administrative CLI commands for authsome."""

import json as json_lib
import os
import sys
from pathlib import Path

import click
from loguru import logger

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
            if ctx_obj.json_output:
                ctx_obj.print_json({"log_file": str(log_path), "entries": raw_lines})
            elif not raw_lines:
                ctx_obj.echo("No log entries found.", err=True, color="yellow")
            else:
                for entry in raw_lines:
                    ctx_obj.emit(entry)
        except FileNotFoundError:
            if ctx_obj.json_output:
                ctx_obj.print_json({"log_file": str(log_path), "entries": []})
            else:
                ctx_obj.echo("No log entries found.", err=True, color="yellow")
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

    if ctx_obj.json_output:
        ctx_obj.print_json({"log_file": str(audit_path), "entries": parsed})
        return

    if not parsed:
        ctx_obj.echo("No audit entries found.", err=True, color="yellow")
        return

    col_widths = {
        "timestamp": max(19, *(len((e.get("timestamp") or "")[:19]) for e in parsed)),
        "event": max(5, *(len(e.get("event") or "-") for e in parsed)),
        "provider": max(8, *(len(e.get("provider") or "-") for e in parsed)),
        "status": max(6, *(len(e.get("status") or "-") for e in parsed)),
    }

    def _row(ts: str, ev: str, prov: str, stat: str, header: bool = False) -> str:
        return (
            f"{ts:<{col_widths['timestamp']}}  "
            f"{ev:<{col_widths['event']}}  "
            f"{prov:<{col_widths['provider']}}  "
            f"{stat:<{col_widths['status']}}"
        ).rstrip()

    ctx_obj.emit(_row("Timestamp", "Event", "Provider", "Status", header=True))
    ctx_obj.emit(
        _row(
            "-" * col_widths["timestamp"],
            "-" * col_widths["event"],
            "-" * col_widths["provider"],
            "-" * col_widths["status"],
        )
    )

    for entry in parsed:
        ts = (entry.get("timestamp") or "")[:19].replace("T", " ")
        ev = entry.get("event") or entry.get("raw") or "-"
        prov = entry.get("provider") or "-"
        stat = entry.get("status") or "-"
        status_color = None
        if not ctx_obj.no_color:
            if stat in ("success", "ok", "completed"):
                status_color = "green"
            elif stat in ("failure", "failed", "error"):
                status_color = "red"
        if status_color:
            stat_str = click.style(stat, fg=status_color)
            ctx_obj.emit(_row(ts, ev, prov, "") + stat_str)
        else:
            ctx_obj.emit(_row(ts, ev, prov, stat))


@admin.command(name="rekey")
@auth_command
async def rekey(ctx_obj: ContextObj) -> None:
    """Generate a new master key and re-encrypt all stored credentials in place."""
    actx = await ctx_obj.initialize()
    if not ctx_obj.json_output and not ctx_obj.quiet:
        ctx_obj.echo("Generating a new master key and re-encrypting the vault...", color="cyan")

    try:
        await actx.runtime_client.rekey()

        if ctx_obj.json_output:
            ctx_obj.print_json({"status": "success", "message": "Master key successfully rotated"})
        else:
            ctx_obj.echo("Master key successfully rotated and credentials re-encrypted.", color="green")

        logger.info("client_event event=rekey status=success")
    except Exception:
        logger.warning("client_event event=rekey status=failure")
        raise


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
        ctx_obj.echo("Daemon is already running.", color="yellow")
        return

    if is_port_occupied(7998):
        ctx_obj.echo("Port 7998 is occupied by an unrelated process. We did not start a new process.", color="yellow")
        return

    try:
        start_daemon()
        await wait_for_daemon_ready(timeout=5)
        ctx_obj.echo("Daemon started successfully.", color="green")
    except DaemonAlreadyRunningError as exc:
        pid_str = f" (PID: {exc.pid})" if exc.pid else ""
        ctx_obj.echo(f"Daemon is already running{pid_str}.", color="yellow")
    except DaemonUnavailableError as exc:
        ctx_obj.echo(str(exc), err=True, color="red")
        sys.exit(1)


@daemon.command(name="stop")
@auth_command
async def daemon_stop(ctx_obj: ContextObj) -> None:
    """Stop the local daemon."""
    stopped, message = await stop_daemon()
    if stopped:
        ctx_obj.echo(message, color="green")
    else:
        ctx_obj.echo(message, err=True, color="yellow")


@daemon.command(name="restart")
@auth_command
async def daemon_restart(ctx_obj: ContextObj) -> None:
    """Restart the local daemon."""
    stopped, message = await stop_daemon()
    if stopped:
        ctx_obj.echo(message, color="green")
    else:
        ctx_obj.echo(message, color="yellow")

    if await is_daemon_responsive():
        ctx_obj.echo("Daemon is already running on port 7998. We did not start a new process.", color="yellow")
        return

    if is_port_occupied(7998):
        ctx_obj.echo("Port 7998 is occupied by an unrelated process. We did not start a new process.", color="yellow")
        return

    try:
        start_daemon()
        await wait_for_daemon_ready(timeout=5)
        if stopped:
            ctx_obj.echo("Daemon restarted successfully.", color="green")
        else:
            ctx_obj.echo("New daemon started.", color="green")
    except DaemonAlreadyRunningError as exc:
        pid_str = f" (PID: {exc.pid})" if exc.pid else ""
        ctx_obj.echo(f"Daemon is already running{pid_str}.", color="yellow")
    except DaemonUnavailableError as exc:
        ctx_obj.echo(str(exc), err=True, color="red")
        sys.exit(1)


@daemon.command(name="status")
@auth_command
async def daemon_status_cmd(ctx_obj: ContextObj) -> None:
    """Show daemon status."""
    status = await daemon_status()
    if ctx_obj.json_output:
        ctx_obj.print_json(status)
    else:
        ctx_obj.echo(json_lib.dumps(status, indent=2))


@daemon.command(name="logs")
@click.option("-n", "--lines", default=80, metavar="COUNT", help="Number of lines to show.")
@auth_command
async def daemon_logs(ctx_obj: ContextObj, lines: int) -> None:
    """Show daemon log output."""
    from authsome.cli.daemon_control import LOG_FILE

    if not LOG_FILE.exists():
        ctx_obj.echo(f"No daemon log found at {LOG_FILE}", err=True, color="yellow")
        return
    for line in LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]:
        ctx_obj.echo(line)
