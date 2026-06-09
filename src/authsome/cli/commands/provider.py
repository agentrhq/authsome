"""Provider CLI commands."""

import pathlib
import sys

import click
import requests
from loguru import logger

from authsome.auth.models.provider import ProviderDefinition
from authsome.cli.context import ContextObj
from authsome.cli.helpers import _validate_provider_endpoints, auth_command
from authsome.utils import format_error_code, parse_jsonc


@click.group(name="provider")
def provider() -> None:
    """Manage provider definitions and provider-level operations."""


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
        provider_definition = ProviderDefinition.model_validate(provider_data)
        conns = connected.get(provider_definition.name, [])
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
            "name": provider_definition.name,
            "display_name": provider_definition.display_name,
            "auth_type": provider_definition.auth_type.value,
            "source": source,
            "connections": connections_out,
        }

    bundled_out = [build_provider_entry(p, "bundled") for p in by_source["bundled"]]
    custom_out = [build_provider_entry(p, "custom") for p in by_source["custom"]]
    ctx_obj.print_json({"bundled": bundled_out, "custom": custom_out})


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
        data = parse_jsonc(filepath.read_text(encoding="utf-8"))
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
