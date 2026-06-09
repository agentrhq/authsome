"""
Authsome — A hosted-by-default authentication library for AI agents and developer tools.

Provides credential management for third-party services with support for:
- OAuth2 (PKCE, Device Code, DCR + PKCE)
- API key management
- Encrypted credential storage

Usage:
    Run `authsome login openai` to connect a provider through the configured
    Authsome server, then use `authsome run ...` to inject credentials through
    the local proxy. Set `AUTHSOME_BASE_URL` to opt into a local or self-hosted
    Authsome server.
"""

from importlib.metadata import PackageNotFoundError as _PkgNotFoundError
from importlib.metadata import version as _pkg_version

from loguru import logger as _logger

from authsome.auth.models.connection import ConnectionRecord, Sensitive
from authsome.auth.models.enums import AuthType, ConnectionStatus, ExportFormat, FlowType
from authsome.auth.models.provider import ProviderDefinition
from authsome.errors import (
    AuthenticationFailedError,
    AuthsomeError,
    ConnectionNotFoundError,
    CredentialMissingError,
    DiscoveryError,
    EncryptionUnavailableError,
    IdentityNotFoundError,
    InputCancelledError,
    InvalidProviderSchemaError,
    ProviderNotFoundError,
    RefreshFailedError,
    StoreUnavailableError,
    TokenExpiredError,
    UnsupportedAuthTypeError,
    UnsupportedFlowError,
)
from authsome.vault import Vault

_logger.disable("authsome")

try:
    __version__ = _pkg_version("authsome")
except _PkgNotFoundError:
    __version__ = "unknown"

__all__ = [
    # Core
    "Vault",
    # Models
    "AuthType",
    "ConnectionRecord",
    "ConnectionStatus",
    "ExportFormat",
    "FlowType",
    "ProviderDefinition",
    "Sensitive",
    # Errors
    "AuthsomeError",
    "AuthenticationFailedError",
    "ConnectionNotFoundError",
    "CredentialMissingError",
    "DiscoveryError",
    "EncryptionUnavailableError",
    "IdentityNotFoundError",
    "InputCancelledError",
    "InvalidProviderSchemaError",
    "ProviderNotFoundError",
    "RefreshFailedError",
    "StoreUnavailableError",
    "TokenExpiredError",
    "UnsupportedAuthTypeError",
    "UnsupportedFlowError",
]
