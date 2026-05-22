"""Advanced and operator-oriented CLI commands."""

from __future__ import annotations

import json as json_lib
import os
import pathlib
import sys
from pathlib import Path

import click
import requests
from loguru import logger

from authsome.auth.models.provider import ProviderDefinition
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
from authsome.cli.helpers import _validate_provider_endpoints, auth_command
from authsome.paths import get_client_log_path, get_server_log_path
from authsome.utils import format_error_code

advanced = click.Group(name="advanced", help="Advanced and operator-oriented commands.")


@advanced.command(name="log")
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


@advanced.command()
@click.argument("provider")
@auth_command
async def remove(ctx_obj: ContextObj, provider: str) -> None:
    """Permanently uninstall the specified custom PROVIDER definition."""
    actx = await ctx_obj.initialize()
    await actx.runtime_client.remove(provider)
    logger.info("client_event event=remove provider={} connection=all", provider)

    if ctx_obj.json_output:
        ctx_obj.print_json({"status": "removed", "provider": provider})
    else:
        ctx_obj.echo(f"Removed provider {provider}.", color="green")


@advanced.command()
@click.argument("path")
@click.option("--force", is_flag=True, help="Force overwrite if provider exists.")
@click.option("--yes", is_flag=True, help="Skip the registration confirmation prompt.")
@auth_command
async def register(ctx_obj: ContextObj, path: str, force: bool, yes: bool) -> None:
    """Register a provider definition from a local JSON file path."""
    actx = await ctx_obj.initialize()
    filepath = pathlib.Path(path)
    if not filepath.exists():
        ctx_obj.echo(f"File not found: {path}", err=True, color="red")
        sys.exit(1)

    try:
        data = json_lib.loads(filepath.read_text(encoding="utf-8"))
        definition = ProviderDefinition.model_validate(data)

        endpoints_to_check = _validate_provider_endpoints(definition, ctx_obj)

        if not ctx_obj.json_output and not ctx_obj.quiet and not yes and not force:
            ctx_obj.echo(f"Registering '{definition.name}' provider:")
            for name, val, _ in endpoints_to_check:
                ctx_obj.echo(f"  - {name}: {val}")

            if definition.oauth and definition.oauth.token_url:
                prompt_msg = f"Register '{definition.name}' with token endpoint {definition.oauth.token_url}? [y/N]"
            elif definition.api_url:
                prompt_msg = f"Register '{definition.name}' with host {definition.api_url}? [y/N]"
            else:
                prompt_msg = f"Register '{definition.name}' provider? [y/N]"

            if not click.confirm(prompt_msg, default=False):
                ctx_obj.echo("Registration aborted.", color="yellow")
                sys.exit(0)

        await actx.runtime_client.register_provider(definition.model_dump(mode="json"), force=force)

        endpoints = [ep for _, ep, _ in endpoints_to_check]
        logger.info("client_event event=register provider={} endpoints={}", definition.name, endpoints)

        if ctx_obj.json_output:
            ctx_obj.print_json({"status": "registered", "provider": definition.name})
        else:
            ctx_obj.echo(f"Provider {definition.name} registered.", color="green")

        warnings = []
        for name, val, is_host in endpoints_to_check:
            if name not in ("api_url", "authorization_url"):
                continue

            target = val
            if is_host and "://" not in target:
                target = f"https://{target}"

            if not ctx_obj.quiet:
                ctx_obj.echo(f"Testing reachability for {name}...", color="cyan")
            try:
                requests.head(target, timeout=5, allow_redirects=True)
            except requests.RequestException as exc:
                warnings.append(f"{name} ({val}) is unreachable: {exc}")

        if warnings and not ctx_obj.quiet:
            for warning in warnings:
                ctx_obj.echo(f"Warning: {warning}", color="yellow")

    except Exception as exc:
        ctx_obj.echo(f"Failed to register provider: {exc}", err=True, color="red")
        sys.exit(format_error_code(exc))


@advanced.group(name="profile")
def profile() -> None:
    """Manage local profiles backed by identity keys."""


@profile.command(name="create")
@click.option("--handle", default=None, metavar="HANDLE", help="Create or reuse a specific local profile handle.")
@auth_command
async def profile_create(ctx_obj: ContextObj, handle: str | None) -> None:
    """Create a local profile keypair."""
    from authsome.identity import create_identity

    home = Path(os.environ.get("AUTHSOME_HOME", str(Path.home() / ".authsome")))
    identity_meta = create_identity(home, handle)

    data = {
        "status": "created",
        "home": str(home),
        "profile": identity_meta.handle,
        "did": identity_meta.did,
        "registration_status": "registered" if identity_meta.registered else "local",
        "switched": True,
    }
    if ctx_obj.json_output:
        ctx_obj.print_json(data)
    else:
        ctx_obj.echo(f"Created local profile {identity_meta.handle}", color="green")
        ctx_obj.echo("Switched to new profile")
        ctx_obj.echo(f"DID: {identity_meta.did}")


@profile.command(name="use")
@click.argument("handle")
@auth_command
async def profile_use(ctx_obj: ContextObj, handle: str) -> None:
    """Select the active local profile."""
    from authsome.cli.client_config import load_client_config, save_client_config
    from authsome.identity import load_identity

    home = Path(os.environ.get("AUTHSOME_HOME", str(Path.home() / ".authsome")))
    identity_meta = load_identity(home, handle)
    save_client_config(home, load_client_config(home).model_copy(update={"active_identity": identity_meta.handle}))

    data = {
        "status": "active",
        "profile": identity_meta.handle,
        "did": identity_meta.did,
    }
    if ctx_obj.json_output:
        ctx_obj.print_json(data)
    else:
        ctx_obj.echo(f"Active profile: {data['profile']}", color="green")
        ctx_obj.echo(f"DID: {data['did']}")


@advanced.command()
@auth_command
async def doctor(ctx_obj: ContextObj) -> None:
    """Run health checks on directory layout and encryption."""
    actx = await ctx_obj.initialize()
    results = await actx.doctor()

    if ctx_obj.json_output:
        ctx_obj.print_json(results)
    else:
        all_ok = results.get("status") == "ready"
        for key, val in results.get("checks", {}).items():
            ok = val == "ok"
            ctx_obj.emit(f"{key}: ", nl=False)
            ctx_obj.emit("OK" if ok else "FAIL", color="green" if ok else "red")
        issues = results.get("issues", [])
        if issues:
            ctx_obj.echo("\nIssues found:", color="red")
            for issue in issues:
                ctx_obj.echo(f" - {issue}", color="red")

        warnings = results.get("warnings", [])
        if warnings:
            ctx_obj.echo("\nWarnings:", color="yellow")
            for warning in warnings:
                ctx_obj.echo(f" - {warning}", color="yellow")

        if not all_ok:
            sys.exit(1)


@advanced.command(name="rekey")
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


@advanced.command()
@click.option("--no-browser", is_flag=True, help="Print the URL instead of opening a browser.")
@auth_command
async def ui(ctx_obj: ContextObj, no_browser: bool) -> None:
    """Open the daemon dashboard in the browser."""
    actx = await ctx_obj.initialize()
    session = await actx.runtime_client.start_ui_session()
    url = session["url"]
    if no_browser:
        ctx_obj.echo(url)
        return

    import webbrowser

    ctx_obj.echo(f"Opening Authsome UI at {url}")
    webbrowser.open(url)


@advanced.group()
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
