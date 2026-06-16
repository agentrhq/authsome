"""Root CLI commands."""

import sys
import webbrowser
from contextlib import suppress
from typing import Any

import click
from loguru import logger

from authsome import FlowType
from authsome.auth.flows.browser import BrowserFlow
from authsome.auth.models.enums import AuthType
from authsome.auth.models.provider import ProviderDefinition
from authsome.cli.config import ClientConfig
from authsome.cli.context import ContextObj
from authsome.cli.helpers import (
    _api_key_env_var,
    _scan_env_sources,
    _scan_resolve_should_import,
    auth_command,
)
from authsome.cli.identity import RuntimeIdentity
from authsome.config import get_authsome_config
from authsome.paths import get_client_log_path
from authsome.utils import connection_is_active


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


async def _run_credential_scan(  # noqa: PLR0912, PLR0915
    actx: ContextObj,
    *,
    connection: str,
    auto_import: bool,
    event_name: str,
) -> dict[str, Any]:
    """Scan env sources for API keys and optionally import them into the vault."""
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
        json_output=actx.json_output,
        quiet=actx.quiet,
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
                "client_event event={} provider={} connection={} source={} source_env={} status=success",
                event_name,
                provider_name,
                connection,
                item["source"],
                item["env_var"],
            )

    return {
        "connection": connection,
        "import": should_import,
        "configured_count": len(configured),
        "imported_count": imported,
        "results": results,
    }


@click.command()
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
async def login(  # noqa: PLR0913
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

            with suppress(Exception):
                webbrowser.open(auth_url)

        elif action_type == "browser":
            credentials = await BrowserFlow.run_login(next_action, provider)
            session_info = await actx.runtime_client.resume_login_session(session_info["id"], credentials=credentials)
            login_result = _build_login_json_payload(session_info, provider, connection)

    logger.info(
        "client_event event=login provider={} connection={} flow={} status={}",
        provider,
        connection,
        flow or "unknown",
        login_result["status"],
    )

    ctx_obj.print_json(login_result)


@click.command(name="onboard")
@click.option(
    "--base-url",
    metavar="URL",
    help="Daemon base URL to use and persist in client config for future commands.",
)
@click.option(
    "--scan-only",
    is_flag=True,
    help="Report env/vault drift without importing discovered keys.",
)
@auth_command
async def onboard(ctx_obj: ContextObj, base_url: str | None, scan_only: bool) -> None:
    """First-run setup: identity, claim, and API key import from env files.

    Idempotent — safe to re-run. Discovered keys matching the vault are skipped.
    """
    if ctx_obj.quiet:
        raise click.UsageError(
            "'onboard' does not support --quiet. Use the default JSON output or omit --scan-only to import."
        )

    home = get_authsome_config().home
    if base_url is not None:
        normalized = base_url.strip().rstrip("/")
        if not normalized:
            raise click.UsageError("--base-url must be a non-empty URL.")
        ClientConfig.load(home).model_copy(update={"daemon_base_url": normalized}).save(home)

    RuntimeIdentity.ensure_local(home)

    actx = await ctx_obj.initialize()
    identity = await actx.runtime_client.ensure_identity_ready()
    whoami_data = await actx.runtime_client.whoami()
    client_config = ClientConfig.load(home)

    scan_result = await _run_credential_scan(
        actx,
        connection="default",
        auto_import=not scan_only,
        event_name="onboard",
    )

    ctx_obj.print_json(
        {
            "status": "onboarded",
            "home": str(home),
            "agent": identity.handle,
            "did": identity.did,
            "registration_status": "registered",
            "daemon_base_url": client_config.daemon_base_url or actx.runtime_client.base_url,
            "configured_encryption_mode": whoami_data.get("configured_encryption_mode"),
            "effective_encryption_source": whoami_data.get("effective_encryption_source"),
            "encryption_backend": whoami_data.get("encryption_backend"),
            **scan_result,
        }
    )


@click.command()
@click.argument("provider")
@click.option("--connection", default="default", metavar="NAME", help="Connection name.")
@auth_command
async def logout(ctx_obj: ContextObj, provider: str, connection: str) -> None:
    """Log out of the specified PROVIDER connection."""
    actx = await ctx_obj.initialize()
    await actx.runtime_client.logout(provider, connection)
    logger.info("client_event event=logout provider={} connection={}", provider, connection)

    ctx_obj.print_json({"status": "logged_out", "provider": provider, "connection": connection})


@click.command(context_settings=dict(ignore_unknown_options=True))
@click.argument("command", nargs=-1, required=True)
@auth_command
async def run(ctx_obj: ContextObj, command: tuple[str]) -> None:
    """Run COMMAND as a subprocess injected with authentication credentials."""
    actx = await ctx_obj.initialize()
    result = await actx.require_local_proxy().run(list(command))
    sys.exit(result.returncode)


@click.command()
@auth_command
async def whoami(ctx_obj: ContextObj) -> None:
    """Show basic local context."""
    actx = await ctx_obj.initialize()

    whoami_data = await actx.runtime_client.whoami()
    doctor_results = await actx.doctor()
    issues = list(doctor_results.get("issues", []))

    vault_status = "OK" if doctor_results.get("status") == "ready" else "ERROR"

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

    agent = whoami_data.get("identity", whoami_data.get("active_identity"))
    data = {
        "authsome_version": whoami_data["version"],
        "home_directory": whoami_data["home"],
        "agent": agent,
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


@click.command()
@auth_command
async def doctor(ctx_obj: ContextObj) -> None:
    """Run health checks on directory layout and encryption."""
    actx = await ctx_obj.initialize()
    results = await actx.doctor()
    all_ok = results.get("status") == "ready"

    ctx_obj.print_json(results)
    if not all_ok:
        sys.exit(1)


@click.command(name="log")
@click.option("-n", "--lines", default=50, metavar="COUNT", help="Number of entries to show.")
@click.option("--raw", is_flag=True, help="Show raw client debug log instead of structured audit entries.")
@auth_command
async def log_cmd(ctx_obj: ContextObj, lines: int, raw: bool) -> None:
    """View structured audit entries or the raw client debug log."""
    home = get_authsome_config().home

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
