"""Command-line interface for authsome."""

from pathlib import Path

import click

from authsome import __version__
from authsome.cli.commands import register_commands
from authsome.cli.context import common_options
from authsome.cli.helpers import setup_logging
from authsome.config import get_authsome_config


@click.group()
@click.version_option(__version__, "-v", "--version")
@click.option("--verbose", is_flag=True, default=False, help="Enable DEBUG logging to stderr.")
@click.option(
    "--log-file",
    "log_file",
    default=str(get_authsome_config().client_log_path),
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


register_commands(cli)


if __name__ == "__main__":
    cli()
