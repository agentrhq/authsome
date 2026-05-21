"""Identity-domain exports.

Contains cryptographic primitives and domain models.
Filesystem-backed registry implementations live in server/registries.py.
"""

from authsome.identity.local import (
    IdentityMetadata,
    IdentityStatus,
    create_identity,
    current_from_home,
    ensure_local_identity,
    identities_dir,
    identity_exists,
    identity_key_path,
    identity_metadata_path,
    load_identity,
    load_private_key,
    mark_claimed,
    mark_registered,
    public_key_from_did_key,
    public_key_to_did_key,
    remove_legacy_default_identity,
    validate_handle,
)
from authsome.identity.principal import (
    ClaimStatus,
    IdentityClaimRecord,
    PrincipalRecord,
    PrincipalVaultBindingRecord,
    VaultRecord,
)
from authsome.identity.proof import (
    POP_AUTH_SCHEME,
    ProofClaims,
    ProofValidationError,
    ReplayCache,
    create_proof_jwt,
    validate_proof_jwt,
)
from authsome.identity.registry import IdentityRegistration

__all__ = [
    "ClaimStatus",
    "IdentityClaimRecord",
    "IdentityMetadata",
    "IdentityStatus",
    "IdentityRegistration",
    "PrincipalRecord",
    "PrincipalVaultBindingRecord",
    "POP_AUTH_SCHEME",
    "ProofClaims",
    "ProofValidationError",
    "ReplayCache",
    "VaultRecord",
    "current_from_home",
    "create_identity",
    "create_proof_jwt",
    "ensure_local_identity",
    "identities_dir",
    "identity_exists",
    "identity_key_path",
    "identity_metadata_path",
    "load_identity",
    "load_private_key",
    "mark_claimed",
    "mark_registered",
    "public_key_from_did_key",
    "public_key_to_did_key",
    "remove_legacy_default_identity",
    "validate_proof_jwt",
    "validate_handle",
]
