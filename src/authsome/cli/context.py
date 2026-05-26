"""CLI Context management and decorators."""

import functools
import json as json_lib
import os
from pathlib import Path
from typing import Any

import click

from authsome.cli.client import AuthsomeApiClient
from authsome.cli.daemon_control import resolve_runtime_client
from authsome.proxy.runner import ProxyRunner


class CliRuntime:
    """CLI-local wiring around the daemon API client."""

    def __init__(self, client: AuthsomeApiClient) -> None:
        self.runtime_client = client
        self.home = Path(os.environ.get("AUTHSOME_HOME", str(Path.home() / ".authsome")))

    async def doctor(self) -> dict[str, Any]:
        return await self.runtime_client.doctor()

    def require_local_proxy(self) -> ProxyRunner:
        return ProxyRunner(client=self.runtime_client, home=self.home)


class ContextObj:
    """Context object passed to all commands."""

    def __init__(self, json_output: bool, quiet: bool, no_color: bool):
        self.json_output = json_output
        self.quiet = quiet
        self.no_color = no_color
        self._ctx: CliRuntime | None = None

    async def initialize(self) -> CliRuntime:
        if self._ctx is None:
            self._ctx = CliRuntime(await resolve_runtime_client())
        return self._ctx

    def print_json(self, data: Any) -> None:
        output = {"v": 1}
        if isinstance(data, dict):
            output.update(data)
        else:
            output["data"] = data
        click.echo(json_lib.dumps(output, indent=2))

    def echo(self, message: str, err: bool = False, color: str | None = None, nl: bool = True) -> None:
        if self.quiet:
            return
        if self.no_color:
            color = None
        click.secho(message, err=err or self.json_output, fg=color, nl=nl)

    def emit(self, message: str, color: str | None = None, nl: bool = True) -> None:
        """Print primary data output. Never suppressed by --quiet; respects --no-color."""
        if self.no_color:
            color = None
        click.secho(message, err=self.json_output, fg=color, nl=nl)


pass_ctx = click.make_pass_decorator(ContextObj)


def common_options(f):
    @click.option("--quiet", is_flag=True, help="Suppress non-essential output.")
    @click.option("--no-color", is_flag=True, help="Disable ANSI colors.")
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        quiet = kwargs.pop("quiet", False)
        no_color = kwargs.pop("no_color", False)
        ctx = click.get_current_context()
        if getattr(ctx, "obj", None) is None:
            ctx.obj = ContextObj(True, quiet, no_color)
        else:
            ctx.obj.json_output = True
            if quiet:
                ctx.obj.quiet = True
            if no_color:
                ctx.obj.no_color = True
        return f(*args, **kwargs)

    return wrapper
