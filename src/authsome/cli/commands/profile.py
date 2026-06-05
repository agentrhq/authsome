"""Profile CLI commands."""

import click

from authsome.cli.config import ClientConfig
from authsome.cli.context import ContextObj
from authsome.cli.helpers import auth_command
from authsome.cli.identity import RuntimeIdentity
from authsome.config import get_authsome_config


@click.group(name="profile")
def profile() -> None:
    """Manage local profiles backed by identity keys."""


@profile.command(name="create")
@click.option("--handle", default=None, metavar="HANDLE", help="Create or reuse a specific local profile handle.")
@auth_command
async def profile_create(ctx_obj: ContextObj, handle: str | None) -> None:
    """Create a local profile keypair."""
    home = get_authsome_config().home
    identity = RuntimeIdentity.create(home, handle)

    data = {
        "status": "created",
        "home": str(home),
        "profile": identity.handle,
        "did": identity.did,
        "registration_status": "local",
        "switched": True,
    }
    ctx_obj.print_json(data)


@profile.command(name="use")
@click.argument("handle")
@auth_command
async def profile_use(ctx_obj: ContextObj, handle: str) -> None:
    """Select the active local profile."""
    home = get_authsome_config().home
    identity = RuntimeIdentity.from_filesystem(home, handle)
    ClientConfig.load(home).model_copy(update={"active_identity": identity.handle}).save(home)

    data = {
        "status": "active",
        "profile": identity.handle,
        "did": identity.did,
    }
    ctx_obj.print_json(data)
