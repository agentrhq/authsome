"""Authsome configuration models and helpers."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from pydantic import BaseModel, Field


def current_spec_version() -> int:
    """Return the config spec version derived from authsome's minor package version."""
    try:
        package_version = version("authsome")
    except PackageNotFoundError:
        return 0
    parts = package_version.split(".")
    if len(parts) < 2:
        return 0
    try:
        return int(parts[1])
    except ValueError:
        return 0


class EncryptionConfig(BaseModel):
    """Vault encryption backend settings for the daemon."""

    mode: str = "auto"


class ServerConfig(BaseModel):
    """Daemon-owned server configuration."""

    spec_version: int = Field(default_factory=current_spec_version)
    encryption: EncryptionConfig = Field(default_factory=EncryptionConfig)

    model_config = {"extra": "allow"}
