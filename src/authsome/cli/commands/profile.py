"""Profile CLI commands."""

import click

from authsome.cli.config import load_client_config, save_client_config
from authsome.cli.context import ContextObj
from authsome.cli.helpers import auth_command
from authsome.cli.identity import create_identity, load_identity
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
    identity_meta = create_identity(home, handle)

    data = {
        "status": "created",
        "home": str(home),
        "profile": identity_meta.handle,
        "did": identity_meta.did,
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
    identity_meta = load_identity(home, handle)
    save_client_config(home, load_client_config(home).model_copy(update={"active_identity": identity_meta.handle}))

    data = {
        "status": "active",
        "profile": identity_meta.handle,
        "did": identity_meta.did,
    }
    ctx_obj.print_json(data)
