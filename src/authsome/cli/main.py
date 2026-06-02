"""Command-line interface for authsome."""

import json
import os
import pathlib
import sys
from pathlib import Path
from typing import Any

import click
import requests
from loguru import logger

from authsome import FlowType, __version__
from authsome.auth.models.enums import AuthType
from authsome.auth.models.provider import ProviderDefinition
from authsome.cli.client import resolve_daemon_url
from authsome.cli.context import ContextObj, common_options
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
from authsome.cli.helpers import (
    _api_key_env_var,
    _scan_env_sources,
    _scan_resolve_should_import,
    _validate_provider_endpoints,
    auth_command,
    setup_logging,
)
from authsome.paths import get_client_log_path
from authsome.utils import connection_is_active, format_error_code, redact


@click.group()
@click.version_option(__version__, "-v", "--version")
@click.option("--verbose", is_flag=True, default=False, help="Enable DEBUG logging to stderr.")
@click.option(
    "--log-file",
    "log_file",
    default=str(get_client_log_path(Path(os.environ.get("AUTHSOME_HOME", str(Path.home() / ".authsome"))))),
    show_default=True,
    metavar="PATH",
    help="Path for the rotating log file. Pass empty string to disable.",
)
@common_options
@click.pass_context
def cli(ctx: click.Context, verbose: bool, log_file: str) -> None:
    """Authsome: Portable local authentication library for AI agents and tools.

    Securely manage credentials and API keys for third-party providers from your terminal.
    """
    resolved = Path(log_file) if log_file else None
    setup_logging(verbose=verbose, log_file=resolved)


@cli.group(name="provider")
def provider() -> None:
    """Manage provider definitions and provider-level operations."""


@cli.group(name="connections")
def connections() -> None:
    """Inspect and manage stored provider connections."""


@provider.command(name="list")
@auth_command
async def list_cmd(ctx_obj: ContextObj) -> None:
    """List configured providers and active connection states."""
    actx = await ctx_obj.initialize()
    data = await actx.runtime_client.list_connections()
    raw_list = data["connections"]
    by_source = data["by_source"]

    connected: dict[str, list[dict]] = {}
    for provider_group in raw_list:
        connected[provider_group["name"]] = provider_group["connections"]

    def build_provider_entry(provider_data, source: str) -> dict:
        provider = ProviderDefinition.model_validate(provider_data)
        conns = connected.get(provider.name, [])
        connections_out = []
        for conn in conns:
            c: dict = {
                "connection_name": conn["connection_name"],
                "is_default": conn.get("is_default", False),
                "auth_type": conn.get("auth_type"),
                "status": conn.get("status"),
            }
            if conn.get("scopes"):
                c["scopes"] = conn["scopes"]
            if conn.get("expires_at"):
                c["expires_at"] = conn["expires_at"]
            connections_out.append(c)
        return {
            "name": provider.name,
            "display_name": provider.display_name,
            "auth_type": provider.auth_type.value,
            "source": source,
            "connections": connections_out,
        }

    bundled_out = [build_provider_entry(p, "bundled") for p in by_source["bundled"]]
    custom_out = [build_provider_entry(p, "custom") for p in by_source["custom"]]
    ctx_obj.print_json({"bundled": bundled_out, "custom": custom_out})


def _build_login_json_payload(session_info: dict[str, Any], provider: str, connection: str) -> dict[str, Any]:
    """Return machine-usable login output for CLI JSON mode."""
    status = session_info.get("status")
    payload: dict[str, Any] = {
        "status": "success" if status == "completed" else "started",
        "provider": provider,
        "connection": connection,
        "record_status": status,
    }
    if session_id := session_info.get("id"):
        payload["session_id"] = session_id
    next_action = session_info.get("next_action")
    if isinstance(next_action, dict) and next_action.get("type") == "open_url":
        auth_url = next_action.get("url")
        if auth_url:
            payload["auth_url"] = auth_url
    for field in ("user_code", "verification_uri", "verification_uri_complete"):
        value = session_info.get(field)
        if value:
            payload[field] = value
    return payload


@cli.command()
@click.argument("provider")
@click.option("--connection", default="default", metavar="NAME", help="Connection name.")
@click.option(
    "--flow",
    type=click.Choice([e.value for e in FlowType], case_sensitive=False),
    metavar="FLOW",
    help=f"Authentication flow override ({', '.join(e.value for e in FlowType)}).",
)
@click.option("--scopes", metavar="SCOPES", help="Comma-separated list of permission scopes to request.")
@click.option("--base-url", metavar="URL", help="Override provider API base URL (e.g. for self-hosted enterprise).")
@click.option("--force", is_flag=True, help="Overwrite an existing connection if it already exists.")
@auth_command
async def login(
    ctx_obj: ContextObj,
    provider: str,
    connection: str,
    flow: str | None,
    scopes: str | None,
    base_url: str | None,
    force: bool,
) -> None:
    """Authenticate with PROVIDER using the configured flow."""
    actx = await ctx_obj.initialize()
    flow_value = FlowType(flow).value if flow else None
    scope_list = [s.strip() for s in scopes.split(",")] if scopes else None

    try:
        session_info = await actx.runtime_client.start_login(
            provider=provider,
            connection=connection,
            flow=flow_value,
            scopes=scope_list,
            base_url=base_url,
            force=force,
        )
        login_result = _build_login_json_payload(session_info, provider, connection)

        if login_result["status"] != "success":
            next_action = session_info.get("next_action", {"type": "none"})
            action_type = next_action.get("type")

            if action_type == "open_url":
                auth_url = next_action["url"]
                import webbrowser

                try:
                    webbrowser.open(auth_url)
                except Exception:
                    pass

            elif action_type == "browser":
                from authsome.auth.flows.browser import BrowserFlow

                credentials = await BrowserFlow.run_login(next_action, provider)
                session_info = await actx.runtime_client.resume_login_session(
                    session_info["id"], credentials=credentials
                )
                login_result = _build_login_json_payload(session_info, provider, connection)

        logger.info(
            "client_event event=login provider={} connection={} flow={} status={}",
            provider,
            connection,
            flow or "unknown",
            login_result["status"],
        )
    except Exception:
        raise

    ctx_obj.print_json(login_result)


@cli.command(name="scan")
@click.option("--connection", default="default", metavar="NAME", help="Connection name.")
@click.option("--import", "auto_import", is_flag=True, help="Import detected keys without interactive prompt.")
@auth_command
async def scan(ctx_obj: ContextObj, connection: str, auto_import: bool) -> None:
    """Scan env files and process env for provider API keys.

    Returns a drift report by default unless ``--import`` is also passed.
    """
    if ctx_obj.quiet:
        raise click.UsageError("'scan' does not support --quiet. Use the default JSON output or --import to apply.")

    actx = await ctx_obj.initialize()
    scanned_env = _scan_env_sources()

    provider_defs: list[ProviderDefinition] = []
    connections = await actx.runtime_client.list_connections()
    by_source = connections.get("by_source", {})
    for source in ("bundled", "custom"):
        for provider_data in by_source.get(source, []):
            provider_defs.append(ProviderDefinition.model_validate(provider_data))

    results: list[dict[str, Any]] = []
    configured: list[dict[str, Any]] = []
    for definition in provider_defs:
        if definition.auth_type != AuthType.API_KEY:
            continue

        existing_record: dict[str, Any] | None = None
        try:
            existing_record = await actx.runtime_client.get_connection(definition.name, connection)
        except Exception:
            existing_record = None

        existing_api_key = existing_record.get("api_key") if existing_record else None
        existing_api_key = existing_api_key.strip() if isinstance(existing_api_key, str) else None
        authsome_has_key = bool(existing_api_key and existing_record and existing_record.get("status") == "connected")

        env_var = _api_key_env_var(definition)
        if not env_var:
            status = "no_env_mapping_authsome_present" if authsome_has_key else "no_env_mapping"
            results.append({"provider": definition.name, "status": status})
            continue

        env_entry = scanned_env.get(env_var)
        env_value_raw = env_entry[0] if env_entry else None
        env_value = env_value_raw.strip() if isinstance(env_value_raw, str) and env_value_raw.strip() else None
        source_name = env_entry[1] if env_entry else None

        if env_value and authsome_has_key:
            drift_status = "env_and_authsome_match" if env_value == existing_api_key else "env_and_authsome_different"
        elif env_value and not authsome_has_key:
            drift_status = "env_only"
        elif not env_value and authsome_has_key:
            drift_status = "authsome_only"
        else:
            drift_status = "both_missing"

        results.append({"provider": definition.name, "status": drift_status, "env_var": env_var, "source": source_name})

        if env_value is None:
            continue

        configured.append(
            {
                "provider": definition.name,
                "env_var": env_var,
                "source": source_name,
                "api_key": env_value,
                "drift": drift_status,
            }
        )

    should_import = _scan_resolve_should_import(
        auto_import=auto_import,
        configured_count=len(configured),
        json_output=ctx_obj.json_output,
        quiet=ctx_obj.quiet,
    )

    imported = 0
    if should_import:
        for item in configured:
            provider_name = item["provider"]
            api_key_value = item["api_key"]
            if item.get("drift") == "env_and_authsome_match":
                results.append(
                    {
                        "provider": provider_name,
                        "status": "skipped_unchanged",
                        "env_var": item["env_var"],
                        "source": item.get("source"),
                    }
                )
                continue

            session_info = await actx.runtime_client.start_login(
                provider=provider_name,
                connection=connection,
                flow=FlowType.API_KEY.value,
                force=True,
            )
            session_id = session_info["id"]
            resume_info = await actx.runtime_client.resume_login_session(session_id, api_key=api_key_value)
            if resume_info.get("status") != "completed":
                session_status = resume_info.get("status")
                raise RuntimeError(
                    f"Import did not complete for provider '{provider_name}' (session status: {session_status})."
                )

            imported += 1
            results.append({"provider": provider_name, "status": "imported", "env_var": item["env_var"]})
            logger.info(
                "client_event event=scan provider={} connection={} source={} source_env={} status=success",
                provider_name,
                connection,
                item["source"],
                item["env_var"],
            )

    ctx_obj.print_json(
        {
            "connection": connection,
            "import": should_import,
            "configured_count": len(configured),
            "imported_count": imported,
            "results": results,
        }
    )


@cli.command()
@click.argument("provider")
@click.option("--connection", default="default", metavar="NAME", help="Connection name.")
@auth_command
async def logout(ctx_obj: ContextObj, provider: str, connection: str) -> None:
    """Log out of the specified PROVIDER connection."""
    actx = await ctx_obj.initialize()
    await actx.runtime_client.logout(provider, connection)
    logger.info("client_event event=logout provider={} connection={}", provider, connection)

    ctx_obj.print_json({"status": "logged_out", "provider": provider, "connection": connection})


@connections.command(name="set-default")
@click.argument("provider")
@click.argument("connection")
@auth_command
async def set_default_connection(ctx_obj: ContextObj, provider: str, connection: str) -> None:
    """Set the default CONNECTION for PROVIDER."""
    actx = await ctx_obj.initialize()
    await actx.runtime_client.set_default_connection(provider, connection)
    ctx_obj.print_json({"status": "ok", "provider": provider, "default_connection": connection})


@provider.command()
@click.argument("provider")
@auth_command
async def revoke(ctx_obj: ContextObj, provider: str) -> None:
    """Reset and delete all stored connections and secrets for PROVIDER."""
    actx = await ctx_obj.initialize()
    await actx.runtime_client.revoke(provider)
    logger.info("client_event event=revoke provider={} connection=all", provider)

    ctx_obj.print_json({"status": "revoked", "provider": provider})


@provider.command()
@click.argument("provider")
@auth_command
async def remove(ctx_obj: ContextObj, provider: str) -> None:
    """Permanently uninstall the specified custom PROVIDER definition."""
    actx = await ctx_obj.initialize()
    await actx.runtime_client.remove(provider)
    logger.info("client_event event=remove provider={} connection=all", provider)

    ctx_obj.print_json({"status": "removed", "provider": provider})


@connections.command(name="inspect")
@click.argument("provider")
@click.option("--connection", default="default", metavar="NAME", help="Connection name.")
@click.option("--field", metavar="FIELD", help="Retrieve only the value of the specified metadata FIELD.")
@auth_command
async def inspect_connection(ctx_obj: ContextObj, provider: str, connection: str, field: str | None) -> None:
    """Retrieve redacted credential and metadata details for PROVIDER."""
    actx = await ctx_obj.initialize()
    # Verify provider exists first to raise ProviderNotFoundError if unknown
    await actx.runtime_client.get_provider(provider)
    record_dict = await actx.runtime_client.get_connection(provider, connection)
    from authsome.auth.models.connection import ConnectionRecord

    record = ConnectionRecord.model_validate(record_dict)
    data = redact(record)
    # Decouple from internal schema fields
    data.pop("schema_version", None)

    if field:
        if field in data:
            ctx_obj.print_json({field: data[field]})
        else:
            ctx_obj.print_json({"error": "FieldNotFound", "message": f"Field '{field}' not found."})
            sys.exit(1)
        return

    ctx_obj.print_json(data)
    sys.exit(0)


@provider.command(name="inspect")
@click.argument("provider")
@auth_command
async def inspect_provider(ctx_obj: ContextObj, provider: str) -> None:
    """Summarize configuration settings and active connections for PROVIDER."""
    actx = await ctx_obj.initialize()
    definition_dict = await actx.runtime_client.get_provider(provider)
    data = definition_dict
    data["connections"] = []
    connections_data = await actx.runtime_client.list_connections()
    for provider_group in connections_data["connections"]:
        if provider_group["name"] == provider:
            data["connections"] = provider_group["connections"]
            break

    data.pop("schema_version", None)
    ctx_obj.print_json(data)


@cli.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("command", nargs=-1, required=True)
@auth_command
async def run(ctx_obj: ContextObj, command: tuple[str]) -> None:
    """Run COMMAND as a subprocess injected with authentication credentials."""
    actx = await ctx_obj.initialize()
    result = await actx.require_local_proxy().run(list(command))
    sys.exit(result.returncode)


@provider.command()
@click.argument("path")
@click.option("--force", is_flag=True, help="Force overwrite if provider exists.")
@click.option("--yes", is_flag=True, help="Skip the registration confirmation prompt.")
@auth_command
async def register(ctx_obj: ContextObj, path: str, force: bool, yes: bool) -> None:
    """Register a provider definition from a local JSON file path."""

    actx = await ctx_obj.initialize()
    filepath = pathlib.Path(path)
    if not filepath.exists():
        ctx_obj.print_json({"error": "FileNotFoundError", "message": f"File not found: {path}"})
        sys.exit(1)

    try:
        data = json.loads(filepath.read_text(encoding="utf-8"))
        definition = ProviderDefinition.model_validate(data)

        endpoints_to_check = _validate_provider_endpoints(definition)

        await actx.runtime_client.register_provider(definition.model_dump(mode="json"), force=force)

        endpoints = [ep for _, ep, _ in endpoints_to_check]
        logger.info("client_event event=register provider={} endpoints={}", definition.name, endpoints)

        warnings = []
        for name, val, is_host in endpoints_to_check:
            if name not in ("api_url", "authorization_url"):
                continue

            target = val
            if is_host and "://" not in target:
                target = f"https://{target}"

            try:
                requests.head(target, timeout=5, allow_redirects=True)
            except requests.RequestException as e:
                warnings.append(f"{name} ({val}) is unreachable: {e}")

        ctx_obj.print_json({"status": "registered", "provider": definition.name, "warnings": warnings})
    except Exception as exc:
        ctx_obj.print_json({"error": exc.__class__.__name__, "message": f"Failed to register provider: {exc}"})
        sys.exit(format_error_code(exc))


@cli.command()
@auth_command
async def init(ctx_obj: ContextObj) -> None:
    """Initialize local storage and register a fresh profile."""
    from authsome.identity import ensure_local_identity

    home = Path(os.environ.get("AUTHSOME_HOME", str(Path.home() / ".authsome")))
    identity = ensure_local_identity(home)

    actx = await ctx_obj.initialize()
    identity = await actx.runtime_client.ensure_identity_ready()
    whoami_data = await actx.runtime_client.whoami()

    data = {
        "status": "initialized",
        "home": str(home),
        "profile": identity.handle,
        "did": identity.did,
        "registration_status": "registered",
        "configured_encryption_mode": whoami_data.get("configured_encryption_mode"),
        "effective_encryption_source": whoami_data.get("effective_encryption_source"),
        "encryption_backend": whoami_data.get("encryption_backend"),
    }
    ctx_obj.print_json(data)


_VALID_PROXY_MODES = ("connected_allow", "connected_deny", "configured_allow", "configured_deny")


@cli.group(name="config")
def config_group() -> None:
    """Read and write caller-local configuration."""


@config_group.command(name="get")
@click.argument("key")
@auth_command
def config_get(ctx_obj: ContextObj, key: str) -> None:
    """Read a caller-local configuration value.

    Supported keys: proxy-mode
    """
    from authsome.cli.client_config import load_client_config

    if key != "proxy-mode":
        ctx_obj.print_json({"error": "UnknownConfigKey", "message": f"Unknown key '{key}'. Valid keys: proxy-mode"})
        sys.exit(1)

    home = Path(os.environ.get("AUTHSOME_HOME", str(Path.home() / ".authsome")))
    config = load_client_config(home)
    ctx_obj.print_json({"proxy_mode": config.proxy_mode})


@config_group.command(name="set")
@click.argument("key")
@click.argument("value")
@auth_command
def config_set(ctx_obj: ContextObj, key: str, value: str) -> None:
    """Write a caller-local configuration value.

    Supported keys: proxy-mode
    Valid proxy-mode values: connected_allow, connected_deny, configured_allow, configured_deny
    """
    from authsome.cli.client_config import load_client_config, save_client_config

    if key != "proxy-mode":
        ctx_obj.print_json({"error": "UnknownConfigKey", "message": f"Unknown key '{key}'. Valid keys: proxy-mode"})
        sys.exit(1)

    if value not in _VALID_PROXY_MODES:
        modes_str = ", ".join(_VALID_PROXY_MODES)
        ctx_obj.print_json(
            {"error": "InvalidProxyMode", "message": f"Invalid proxy mode '{value}'. Valid modes: {modes_str}"}
        )
        sys.exit(1)

    home = Path(os.environ.get("AUTHSOME_HOME", str(Path.home() / ".authsome")))
    updated = load_client_config(home).model_copy(update={"proxy_mode": value})
    save_client_config(home, updated)
    ctx_obj.print_json({"proxy_mode": updated.proxy_mode, "status": "ok"})


@cli.group(name="profile")
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
    ctx_obj.print_json(data)


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
    ctx_obj.print_json(data)


@cli.command()
@auth_command
async def whoami(ctx_obj: ContextObj) -> None:
    """Show basic local context."""
    actx = await ctx_obj.initialize()

    # Get info from daemon
    whoami_data = await actx.runtime_client.whoami()
    doctor_results = await actx.doctor()
    issues = list(doctor_results.get("issues", []))

    vault_status = "OK" if doctor_results.get("status") == "ready" else "ERROR"

    # Connected providers with counts
    connected_providers = []
    try:
        connections_data = await actx.runtime_client.list_connections()
        for provider_group in connections_data["connections"]:
            active_conns = [c["connection_name"] for c in provider_group["connections"] if connection_is_active(c)]
            if active_conns:
                connected_providers.append(
                    {
                        "name": provider_group["name"],
                        "count": len(active_conns),
                        "connections": active_conns,
                    }
                )
    except Exception as exc:
        issues.append(f"connections: {exc}")
        vault_status = "ERROR"

    data = {
        "authsome_version": whoami_data["version"],
        "home_directory": whoami_data["home"],
        "profile": whoami_data.get("identity", whoami_data.get("active_identity")),
        "principal_id": whoami_data.get("principal_id"),
        "vault_id": whoami_data.get("vault_id"),
        "did": whoami_data.get("did"),
        "registration_status": whoami_data.get("registration_status"),
        "daemon_url": whoami_data.get("daemon_url", actx.runtime_client.base_url),
        "configured_encryption_mode": whoami_data.get("configured_encryption_mode"),
        "effective_encryption_source": whoami_data.get("effective_encryption_source"),
        "encryption_backend": whoami_data["encryption_backend"],
        "vault_status": vault_status,
        "connected_providers_count": len(connected_providers),
        "connected_providers": connected_providers,
        "issues": issues,
    }

    ctx_obj.print_json(data)


@cli.command()
@auth_command
async def doctor(ctx_obj: ContextObj) -> None:
    """Run health checks on directory layout and encryption."""
    actx = await ctx_obj.initialize()
    results = await actx.doctor()
    all_ok = results.get("status") == "ready"

    ctx_obj.print_json(results)
    if not all_ok:
        sys.exit(1)


@cli.command(name="log")
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

    actx = await ctx_obj.initialize()
    events = await actx.runtime_client.list_audit_events(limit=lines)
    ctx_obj.print_json(events)


@cli.group(name="daemon")
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


if __name__ == "__main__":
    cli()
