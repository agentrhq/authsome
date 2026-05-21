"""Tests for utils.py."""

from datetime import UTC, datetime

import pytest

from authsome.utils import (
    StoreKeyParts,
    build_store_key,
    is_filesystem_safe,
    parse_rfc3339,
    parse_store_key,
    to_rfc3339,
    utc_now,
)


def test_utc_now():
    now = utc_now()
    assert now.tzinfo == UTC


def test_to_rfc3339():
    dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)
    assert to_rfc3339(dt) == "2023-01-01T12:00:00Z"

    # Test dt without tzinfo
    dt_naive = datetime(2023, 1, 1, 12, 0, 0)
    assert to_rfc3339(dt_naive) == "2023-01-01T12:00:00Z"


def test_parse_rfc3339():
    s = "2023-01-01T12:00:00Z"
    dt = parse_rfc3339(s)
    assert dt.tzinfo == UTC

    s_offset = "2023-01-01T12:00:00+00:00"
    dt_offset = parse_rfc3339(s_offset)
    assert dt_offset.tzinfo.utcoffset(dt_offset).total_seconds() == 0


def test_is_filesystem_safe():
    assert is_filesystem_safe("valid-name_1.2") is True
    # Test empty name
    assert is_filesystem_safe("") is False
    assert is_filesystem_safe(None) is False
    # Test path traversal
    assert is_filesystem_safe("bad/name") is False
    assert is_filesystem_safe("bad..name") is False
    assert is_filesystem_safe("bad\\name") is False
    assert is_filesystem_safe(".hidden") is False


def test_build_store_key():
    # Test definition key
    assert build_store_key(record_type="definition", provider="github") == "provider:github:definition"
    assert build_store_key(vault="vault_default", provider="github", record_type="metadata") == (
        "vault:vault_default:github:metadata"
    )
    # Test metadata key
    assert (
        build_store_key(identity="default", provider="github", record_type="metadata")
        == "identity:default:github:metadata"
    )
    # Test state key
    assert (
        build_store_key(identity="default", provider="github", record_type="state") == "identity:default:github:state"
    )
    # Test connection key
    assert (
        build_store_key(
            identity="default",
            provider="github",
            record_type="connection",
            connection="personal",
        )
        == "identity:default:github:connection:personal"
    )
    # Test client key
    assert (
        build_store_key(identity="default", provider="github", record_type="client") == "identity:default:github:client"
    )
    # Test server-scoped client key
    assert build_store_key(provider="github", record_type="server") == "server:provider:github:client"
    # Test value error
    with pytest.raises(ValueError):
        build_store_key(identity="default", provider="github", record_type="unknown")

    # Test missing provider with identity
    with pytest.raises(ValueError):
        build_store_key(identity="default", record_type="metadata")


def test_parse_store_key_server() -> None:
    assert parse_store_key("server:provider:github:client") == StoreKeyParts(
        vault=None,
        identity=None,
        provider="github",
        record_type="server",
        connection=None,
    )
