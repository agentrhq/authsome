"""Tests for errors.py."""

from authsome.errors import (
    AuthenticationFailedError,
    AuthsomeError,
    ConnectionNotFoundError,
    CredentialMissingError,
    DiscoveryError,
    EncryptionUnavailableError,
    IdentityNotFoundError,
    InvalidProviderSchemaError,
    ProviderNotFoundError,
    RefreshFailedError,
    StoreUnavailableError,
    TokenExpiredError,
    UnsupportedAuthTypeError,
    UnsupportedFlowError,
)


def test_authsome_error_formatting():
    # Test operation present
    err = AuthsomeError("message", operation="test_op")
    assert str(err) == "AuthsomeError: (test_op) message"

    # Test provider present
    err2 = AuthsomeError("message", provider="github")
    assert str(err2) == "AuthsomeError: [github] message"


def test_unsupported_auth_type_error():
    err = UnsupportedAuthTypeError("magic", provider="github")
    assert "Unsupported auth type: magic" in str(err)
    assert "[github]" in str(err)


def test_unsupported_flow_error():
    err = UnsupportedFlowError("unknown", provider="github")
    assert "Unsupported flow: unknown" in str(err)


def test_credential_missing_error():
    err = CredentialMissingError(provider="github")
    assert "Credential not found" in str(err)


def test_token_expired_error():
    err = TokenExpiredError(provider="github")
    assert "Access token expired" in str(err)


def test_refresh_failed_error():
    err = RefreshFailedError(provider="github")
    assert "Token refresh failed: Unknown error" in str(err)


def test_encryption_unavailable_error():
    err = EncryptionUnavailableError()
    assert "Encryption backend unavailable" in str(err)


def test_store_unavailable_error():
    err = StoreUnavailableError()
    assert "Credential store unavailable" in str(err)


def test_discovery_error():
    err = DiscoveryError("timeout", provider="github")
    assert "Discovery failed: timeout" in str(err)


def test_provider_not_found_error():
    err = ProviderNotFoundError("missing")
    assert "Provider 'missing' not found" in str(err)


def test_invalid_provider_schema_error():
    err = InvalidProviderSchemaError("bad json", provider="github")
    assert "Invalid provider schema: bad json" in str(err)


def test_identity_not_found_error():
    err = IdentityNotFoundError("work")
    assert "Identity 'work' not found" in str(err)


def test_connection_not_found_error():
    err = ConnectionNotFoundError(provider="github", connection="work", identity="default")
    assert "Connection 'work' not found for provider 'github' in identity 'default'" in str(err)


def test_authentication_failed_error():
    err = AuthenticationFailedError("invalid credentials", provider="github")
    assert "Authentication failed: invalid credentials" in str(err)
