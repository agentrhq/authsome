# Principal-owned vaults, opaque VaultId namespace, and four-registry model

The original design scoped the vault namespace to an Identity (agent) — one credential namespace per agent. This conflated "the thing that holds a cryptographic key" with "the thing that owns credentials." In practice, a human wants multiple agents to share the same GitHub connection without copying tokens. It also left no room for a Principal to hold multiple separate credential stores (e.g., `prod` vs `dev`).

We introduce two new first-class concepts:

**Principal** — a non-cryptographic logical partition (human or team) that owns Vaults and performs OAuth authorization. Identified by an opaque **PrincipalId** (e.g., `principal_abc123def456`). Has no cryptographic key of its own. Every Identity registers under exactly one Principal via a **Claim** recorded in `IdentityClaimRecord`.

**Vault** — a named credential store owned by exactly one Principal via a **PrincipalVaultBinding**. Identified by an opaque **VaultId** (e.g., `vault_a1b2c3d4e5f6`). Vault keys use `vault:<vault_id>:...` — a single opaque segment, not `vault:<principal_handle>:<vault_handle>:...`. All accepted agents bound to the same Vault share its credentials.

Every audit event records both `identity` (which agent acted) and `principal_id` (on whose behalf).

`AuthService` is constructed with `(vault, identity, principal_id, vault_id)`: `vault_id` drives the vault collection (`vault:<vault_id>`); `identity` is carried for audit logging and `principal_id` for ownership context. The caller (daemon dependency injection) resolves `vault_id` from the `PrincipalVaultBindingRegistry` before constructing `AuthService` — `AuthService` is a pure credential-access layer and must never fall back to the identity handle as a vault namespace.

The full domain model is tracked across four separate registry files, each authoritative for one entity type: `principals.json` (`PrincipalRegistry`), `vaults.json` (`VaultRegistry`), `identity_claims.json` (`IdentityClaimRegistry`), `principal_vault_bindings.json` (`PrincipalVaultBindingRegistry`). Relationships are expressed via `IdentityClaimRecord.principal_id` and `PrincipalVaultBindingRecord.{principal_id, vault_id}`. No denormalized reverse-index lists are maintained on the Principal entry.

In local mode a single `default` Vault is created automatically during `authsome init` and bound to a `default` Principal; the resulting opaque `vault_id` is stored in client config so the daemon always passes a concrete id. Multiple vaults per principal are not exposed in any CLI or API in this release; the registry schema supports the extension without a breaking key restructure. In hosted mode, `authsome init --email <email>` registers a **Claim** (`IdentityClaimRecord`) with `claim_status = pending`. The Principal reviews pending claims in the UI and accepts or rejects them. A pending agent can authenticate to the daemon but all vault access is gated until the claim is accepted.

## Considered alternatives

**Identity-scoped vault with a parent pointer**: keep `identity:<handle>:...` keys but add a `principal` back-reference. Rejected because it requires either copying tokens across agents or adding an indirection layer — both create drift.

**Email as vault key**: use the Principal's email directly as the namespace key. Rejected because email addresses can change and are awkward in storage keys.

**`vault:<principal_handle>:<vault_handle>:...` (human-readable two-segment key)**: encode the PrincipalHandle and a human-readable VaultHandle directly in the storage key. Rejected because it ties the storage namespace to human-readable identifiers that can change (handle renames, vault renames) and prevents reassigning a vault between principals without rewriting all stored keys. An opaque VaultId is stable regardless of ownership or naming changes.

**Per-vault encryption key**: give each Vault its own AES-256-GCM master key for cryptographic isolation between `prod` and `dev`. Rejected as premature — one master key with namespace isolation is sufficient; the registry schema is vault-key-ready when the need arises.

**Three-registry model (`principals.json`, `identities.json`, `vaults.json`)**: express the Principal→Vault relationship as a forward key `VaultRegistration.principal_handle`. Rejected in favour of a dedicated `PrincipalVaultBindingRegistry` that makes the binding an explicit, queryable, first-class record — supporting `is_default` and future multi-vault scenarios without embedding list fields on the Principal entry.

## Consequences

Breaking change — existing vault data under `identity:<handle>:...` is not migrated. Users re-run `authsome login` after upgrading. `AuthService` must always be constructed with an explicit `vault_id`; the identity-handle fallback (`vault_id or identity`) is a temporary stopgap to be removed once vault provisioning is wired through `authsome init`. Per-agent credential visibility filtering is deferred to the policy layer.
