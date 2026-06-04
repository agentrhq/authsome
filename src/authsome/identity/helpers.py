"""Identity domain models and did:key helpers."""

import random
import re
from dataclasses import dataclass
from datetime import UTC, datetime

import base58
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from pydantic import BaseModel, Field

_ED25519_MULTICODEC_PREFIX = b"\xed\x01"
_DID_KEY_PREFIX = "did:key:z"
_HANDLE_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")

# TODO: The list is very small, will start creating conflicts soon. Use a library like randomword.
_ADJECTIVES = (
    "brisk",
    "calm",
    "clear",
    "eager",
    "fresh",
    "gentle",
    "honest",
    "kind",
    "lively",
    "quiet",
    "rapid",
    "steady",
    "swift",
    "vivid",
)
_ADVERBS = (
    "boldly",
    "brightly",
    "clearly",
    "deeply",
    "easily",
    "firmly",
    "gladly",
    "lightly",
    "quickly",
    "smoothly",
    "warmly",
    "wisely",
)


class IdentityMetadata(BaseModel):
    """Identity metadata associated with a caller-owned private key."""

    handle: str
    did: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class IdentityMaterial:
    """New identity metadata and its private signing key."""

    metadata: IdentityMetadata
    signer: Ed25519PrivateKey


def generate_handle() -> str:
    """Generate a human-readable identity handle."""
    return "-".join(
        (
            random.choice(_ADJECTIVES),
            random.choice(_ADVERBS),
            random.choice(_ADVERBS),
            f"{random.SystemRandom().randint(0, 9999):04d}",
        )
    )


def validate_handle(handle: str) -> str:
    if not _HANDLE_RE.match(handle):
        raise ValueError(f"Invalid identity handle: {handle}")
    return handle


def public_key_to_did_key(public_key: Ed25519PublicKey) -> str:
    raw = public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return _DID_KEY_PREFIX + base58.b58encode(_ED25519_MULTICODEC_PREFIX + raw).decode("ascii")


def public_key_from_did_key(did: str) -> Ed25519PublicKey:
    if not did.startswith(_DID_KEY_PREFIX):
        raise ValueError("Only did:key Ed25519 identifiers are supported")
    try:
        decoded = base58.b58decode(did[len(_DID_KEY_PREFIX) :])
    except ValueError as exc:
        raise ValueError("Malformed did:key value") from exc
    if not decoded.startswith(_ED25519_MULTICODEC_PREFIX):
        raise ValueError("did:key does not use the Ed25519 multicodec prefix")
    raw_key = decoded[len(_ED25519_MULTICODEC_PREFIX) :]
    if len(raw_key) != 32:
        raise ValueError("Ed25519 did:key public key must be 32 bytes")
    return Ed25519PublicKey.from_public_bytes(raw_key)


def private_key_to_hex(signer: Ed25519PrivateKey) -> str:
    raw = signer.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return raw.hex()


def private_key_from_hex(value: str) -> Ed25519PrivateKey:
    try:
        raw = bytes.fromhex(value.strip())
    except ValueError as exc:
        raise ValueError("Malformed Ed25519 private key hex") from exc
    if len(raw) != 32:
        raise ValueError("Ed25519 private key must be 32 bytes")
    return Ed25519PrivateKey.from_private_bytes(raw)


def create_identity_material(handle: str, signer: Ed25519PrivateKey | None = None) -> IdentityMaterial:
    """Create new in-memory identity metadata and signing key material."""
    resolved_signer = signer or Ed25519PrivateKey.generate()
    now = datetime.now(UTC)
    return IdentityMaterial(
        metadata=IdentityMetadata(
            handle=validate_handle(handle),
            did=public_key_to_did_key(resolved_signer.public_key()),
            created_at=now,
            updated_at=now,
        ),
        signer=resolved_signer,
    )
