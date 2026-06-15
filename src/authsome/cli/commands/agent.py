"""Local agent CLI commands."""

import click

from authsome.cli.config import ClientConfig
from authsome.cli.context import ContextObj
from authsome.cli.helpers import auth_command
from authsome.cli.identity import RuntimeIdentity
from authsome.config import get_authsome_config


@click.group(name="agent")
def agent() -> None:
    """Manage local agents backed by signing keys."""


async def _create_agent(ctx_obj: ContextObj, handle: str | None) -> None:
    home = get_authsome_config().home
    identity = RuntimeIdentity.create(home, handle)

    data = {
        "status": "created",
        "home": str(home),
        "agent": identity.handle,
        "did": identity.did,
        "registration_status": "local",
        "switched": True,
    }
    ctx_obj.print_json(data)


async def _use_agent(ctx_obj: ContextObj, handle: str) -> None:
    home = get_authsome_config().home
    identity = RuntimeIdentity.from_filesystem(home, handle)
    ClientConfig.load(home).model_copy(update={"active_identity": identity.handle}).save(home)

    data = {
        "status": "active",
        "agent": identity.handle,
        "did": identity.did,
    }
    ctx_obj.print_json(data)


@agent.command(name="create")
@click.option("--handle", default=None, metavar="HANDLE", help="Create or reuse a specific local agent handle.")
@auth_command
async def agent_create(ctx_obj: ContextObj, handle: str | None) -> None:
    """Create a local agent keypair."""
    await _create_agent(ctx_obj, handle)


@agent.command(name="use")
@click.argument("handle")
@auth_command
async def agent_use(ctx_obj: ContextObj, handle: str) -> None:
    """Select the active local agent."""
    await _use_agent(ctx_obj, handle)
