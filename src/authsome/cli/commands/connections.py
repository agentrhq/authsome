"""Connection CLI commands."""

import sys

import click

from authsome.auth.models.connection import ConnectionRecord
from authsome.cli.context import ContextObj
from authsome.cli.helpers import auth_command
from authsome.utils import redact


@click.group(name="connections")
def connections() -> None:
    """Inspect and manage stored provider connections."""


@connections.command(name="set-default")
@click.argument("provider")
@click.argument("connection")
@auth_command
async def set_default_connection(ctx_obj: ContextObj, provider: str, connection: str) -> None:
    """Set the default CONNECTION for PROVIDER."""
    actx = await ctx_obj.initialize()
    await actx.runtime_client.set_default_connection(provider, connection)
    ctx_obj.print_json({"status": "ok", "provider": provider, "default_connection": connection})


@connections.command(name="set-global")
@click.argument("provider")
@click.argument("connection")
@auth_command
async def set_global_connection(ctx_obj: ContextObj, provider: str, connection: str) -> None:
    """Make CONNECTION the global fallback for PROVIDER."""
    actx = await ctx_obj.initialize()
    result = await actx.runtime_client.set_global_connection(provider, connection)
    ctx_obj.print_json(result)


@connections.command(name="unset-global")
@click.argument("provider")
@auth_command
async def unset_global_connection(ctx_obj: ContextObj, provider: str) -> None:
    """Remove PROVIDER's global fallback connection."""
    actx = await ctx_obj.initialize()
    result = await actx.runtime_client.unset_global_connection(provider)
    ctx_obj.print_json(result)


@connections.command(name="inspect")
@click.argument("provider")
@click.option("--connection", default="default", metavar="NAME", help="Connection name.")
@click.option("--field", metavar="FIELD", help="Retrieve only the value of the specified metadata FIELD.")
@auth_command
async def inspect_connection(ctx_obj: ContextObj, provider: str, connection: str, field: str | None) -> None:
    """Retrieve redacted credential and metadata details for PROVIDER."""
    actx = await ctx_obj.initialize()
    await actx.runtime_client.get_provider(provider)
    record_dict = await actx.runtime_client.get_connection(provider, connection)

    record = ConnectionRecord.model_validate(record_dict)
    data = redact(record)
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
