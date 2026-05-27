"""CLI specific utilities for authsome."""

import functools
import ipaddress
import os
import sys
import urllib.parse
from pathlib import Path
from typing import Any

import click
from loguru import logger

from authsome.auth.models.provider import ProviderDefinition
from authsome.cli.context import ContextObj, common_options, pass_ctx
from authsome.utils import format_error_code


def handle_errors(func):
    """Catch exceptions and return structured JSON errors."""

    @functools.wraps(func)
    def wrapper(ctx_obj: ContextObj, *args, **kwargs):
        import asyncio
        import inspect

        try:
            if inspect.iscoroutinefunction(func):
                return asyncio.run(func(ctx_obj, *args, **kwargs))
            return func(ctx_obj, *args, **kwargs)
        except Exception as exc:
            ctx_obj.print_json({"error": exc.__class__.__name__, "message": str(exc)})
            sys.exit(format_error_code(exc))

    return wrapper


def auth_command(func):
    """Composite decorator combining common options, context injection, and error handling."""
    return common_options(pass_ctx(handle_errors(func)))


def setup_logging(verbose: bool, log_file: Path | None) -> None:
    """Enable authsome library logs and wire up sinks. CLI-only — never called from library code."""
    logger.remove()
    logger.enable("authsome")

    level = "DEBUG" if verbose else "WARNING"
    logger.add(sys.stderr, level=level, colorize=True, diagnose=False)
    if verbose:
        logger.debug("Verbose logging enabled.")

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            str(log_file),
            level="DEBUG",
            rotation="10 MB",
            retention=5,
            compression="zip",
            diagnose=False,
        )


def _validate_provider_endpoints(definition: Any) -> list[tuple[str, str, bool]]:
    """Extract and validate provider endpoints for security."""
    endpoints_to_check: list[tuple[str, str, bool]] = []
    if definition.oauth:
        if definition.oauth.authorization_url:
            endpoints_to_check.append(("authorization_url", definition.oauth.authorization_url, False))
        if definition.oauth.token_url:
            endpoints_to_check.append(("token_url", definition.oauth.token_url, False))
        if definition.oauth.revocation_url:
            endpoints_to_check.append(("revocation_url", definition.oauth.revocation_url, False))
        if definition.oauth.device_authorization_url:
            endpoints_to_check.append(("device_authorization_url", definition.oauth.device_authorization_url, False))
    if definition.registration and definition.registration.registration_endpoint:
        endpoints_to_check.append(("registration_endpoint", definition.registration.registration_endpoint, False))
    if definition.api_url:
        api_urls = definition.api_url if isinstance(definition.api_url, list) else [definition.api_url]
        for api_url in api_urls:
            endpoints_to_check.append(("api_url", api_url, True))

    for name, val, is_host in endpoints_to_check:
        if "://" in val:
            parsed = urllib.parse.urlparse(val)
            if parsed.scheme != "https":
                raise click.ClickException(f"{name} must use HTTPS scheme ({val})")
            host = parsed.hostname
        else:
            host = val

        if host in ("localhost", "127.0.0.1", "::1"):
            raise click.ClickException(f"{name} cannot be localhost ({val})")

        if host:
            try:
                ipaddress.ip_address(host)
                raise click.ClickException(f"{name} cannot be a bare IP address ({val})")
            except ValueError:
                pass

    return endpoints_to_check


def _api_key_env_var(definition: ProviderDefinition) -> str | None:
    """Return the canonical API key environment variable for a provider."""
    if definition.api_key:
        env_var = getattr(definition.api_key, "env_var", None)
        if isinstance(env_var, str) and env_var.strip():
            return env_var.strip()

    if definition.export and definition.export.env:
        env_var = definition.export.env.get("api_key")
        if env_var and env_var.strip():
            return env_var.strip()

    return None


def _load_dotenv(path: Path) -> dict[str, str]:
    """Parse .env-style files into key/value pairs."""
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value

    return values


def _scan_env_sources() -> dict[str, tuple[str, str]]:
    """Return env values from .env, .env.prod, and process env."""
    scanned: dict[str, tuple[str, str]] = {}

    for key, value in _load_dotenv(Path(".env")).items():
        scanned[key] = (value, ".env")
    for key, value in _load_dotenv(Path(".env.prod")).items():
        scanned[key] = (value, ".env.prod")
    for key, value in os.environ.items():
        scanned[key] = (value, "environment")

    return scanned


def _scan_resolve_should_import(
    *,
    auto_import: bool,
    configured_count: int,
    json_output: bool,
    quiet: bool,
) -> bool:
    """Decide whether to import: explicit flag or interactive confirmation."""
    if auto_import:
        return True
    if configured_count == 0:
        return False
    if json_output:
        return False
    if quiet:
        return False
    return click.confirm(f"Found {configured_count} configured provider(s). Import now?", default=True)
