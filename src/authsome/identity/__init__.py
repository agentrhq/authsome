"""Identity-domain exports."""

from authsome.identity.helpers import (
    IdentityMaterial,
    IdentityMetadata,
    create_identity_material,
    generate_handle,
    private_key_from_hex,
    private_key_to_hex,
    public_key_from_did_key,
    public_key_to_did_key,
    validate_handle,
)
from authsome.identity.principal import (
    ClaimStatus,
    IdentityClaimRecord,
    PrincipalRecord,
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
    "IdentityMaterial",
    "IdentityMetadata",
    "IdentityRegistration",
    "PrincipalRecord",
    "POP_AUTH_SCHEME",
    "ProofClaims",
    "ProofValidationError",
    "ReplayCache",
    "create_identity_material",
    "create_proof_jwt",
    "generate_handle",
    "private_key_from_hex",
    "private_key_to_hex",
    "public_key_from_did_key",
    "public_key_to_did_key",
    "validate_proof_jwt",
    "validate_handle",
]
