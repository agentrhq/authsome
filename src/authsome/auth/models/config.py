"""Authsome configuration models and helpers."""

from importlib.metadata import PackageNotFoundError, version

from pydantic import BaseModel, Field

_MIN_VERSION_PARTS = 2


# TODO: This is generic package level function, move it there
def current_spec_version() -> int:
    """Return the config spec version derived from authsome's minor package version."""
    try:
        package_version = version("authsome")
    except PackageNotFoundError:
        return 0
    parts = package_version.split(".")
    if len(parts) < _MIN_VERSION_PARTS:
        return 0
    try:
        return int(parts[1])
    except ValueError:
        return 0


# TODO: This isn't a property of auth module
class ServerConfig(BaseModel):
    """Daemon-owned server configuration."""

    spec_version: int = Field(default_factory=current_spec_version)

    model_config = {"extra": "allow"}
