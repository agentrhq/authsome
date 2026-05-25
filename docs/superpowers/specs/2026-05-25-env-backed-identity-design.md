# Env-Backed Runtime Identity Design

## Summary

Authsome currently assumes an acting identity is backed by local files under
`~/.authsome/client/identities/` plus a caller-local `active_identity` pointer
in `~/.authsome/client/config.json`. That works for a single developer machine,
but it breaks down for sandboxed agents that do not have a writable or even
readable filesystem.

This design adds env-backed identities as a first-class runtime identity source.
The goal is to let each process supply its own `handle` and optional private key
without changing the server's identity, ownership, or vault model.

## Goals

- Support agents running without a writable filesystem.
- Support multiple parallel agents using different identities in separate
  processes.
- Preserve existing filesystem-backed behavior for local developer workflows.
- Keep the daemon authoritative for registration and claim state.
- Keep the change surface small and focused on identity resolution.

## Non-Goals

- Replacing filesystem-backed identities.
- Changing hosted or local ownership semantics.
- Persisting env-backed identities to disk automatically.
- Introducing a new import/export identity workflow in this change.
- Changing vault namespacing, principal resolution, or server registries.

## Current State

Today the CLI resolves an acting identity from local files and signs PoP JWTs
with a private key loaded from disk.

Relevant current behavior:

- `src/authsome/identity/local.py` persists:
  - `~/.authsome/client/identities/<handle>.key`
  - `~/.authsome/client/identities/<handle>.json`
- `src/authsome/cli/client_config.py` stores `active_identity`.
- `src/authsome/cli/client.py`:
  - supports `AUTHSOME_IDENTITY` as a handle override
  - loads the private key from disk before signing PoP JWTs
  - uses local identity metadata to avoid redundant register/claim calls for
    filesystem identities
- The daemon registry remains authoritative for handle-to-DID mapping.
- Local deployments already resolve all identities into the implicit local
  principal via `LocalOwnershipResolver`.

## User-Facing Behavior

Runtime identity resolution follows this precedence order:

1. If `AUTHSOME_IDENTITY` and `AUTHSOME_IDENTITY_PRIVATE_KEY` are both set,
   treat the process identity as fully env-backed.
2. If only `AUTHSOME_IDENTITY` is set, treat it as a local handle override:
   load that handle from the filesystem when it exists, or create that named
   local identity when it does not.
3. If neither env var is set, fall back to the existing active filesystem
   identity flow.

Invalid partial configuration:

- If `AUTHSOME_IDENTITY_PRIVATE_KEY` is set without `AUTHSOME_IDENTITY`, fail
  fast with a clear error.

Behavior by identity source:

- Filesystem-backed identities keep current behavior, including local metadata
  checks for `registered` and `claimed` state.
- Env-backed identities are fully ephemeral on the client:
  - no metadata file writes
  - no key file writes
  - no `active_identity` updates
  - no local claim-status persistence
- Env-backed identities may make redundant registration or claim-status calls;
  this is acceptable for the ephemeral path.

## Runtime Identity Model

Introduce a runtime-only identity object that is separate from the persisted
`IdentityMetadata` model.

Proposed fields:

- `handle: str`
- `did: str`
- `signer: Ed25519PrivateKey`
- `source: Literal["env", "filesystem"]`

This object represents the acting signer for the current process. It is not a
persisted domain model and should not be written to disk.

`IdentityMetadata` remains the filesystem-backed model for local identities.

## Resolution Rules

### Full env mode

When both env vars are present:

- `handle` comes from `AUTHSOME_IDENTITY`
- `private_key` comes from `AUTHSOME_IDENTITY_PRIVATE_KEY`
- `did` is derived at runtime from the private key's public key
- no filesystem reads or writes are required for key or metadata

### Handle override mode

When only `AUTHSOME_IDENTITY` is present:

- treat the value as a local handle override
- load that handle's metadata and private key from filesystem-backed identity
  storage when it exists
- create that named filesystem-backed identity when it does not exist
- preserve existing filesystem metadata behavior

### Default filesystem mode

When neither env var is present:

- use `active_identity` from caller-local config
- if needed, create/bootstrap a local filesystem identity exactly as today

### Source isolation rule

Do not mix identity sources within one resolved runtime identity.

- In full env mode, `did` and signing key come only from env-backed runtime
  state.
- In handle override mode, metadata and signing key come only from the
  filesystem identity for that handle.

## Client Flow Changes

The CLI and proxy-facing client should stop assuming the acting identity always
comes from local files.

Instead, client code should:

1. Resolve the active runtime identity.
2. Use the runtime private key for PoP signing.
3. Use the runtime `handle` and `did` for registration/bootstrap.
4. Preserve existing metadata shortcut behavior only for filesystem identities.

Expected behavior in `ensure_identity_ready()`:

- Filesystem identity:
  - keep current optimization using local `registered` / `claimed` metadata
  - keep current `mark_registered()` / `mark_claimed()` behavior
- Env identity:
  - skip local metadata checks and writes
  - register if needed using `handle + did`
  - query daemon status when claim readiness must be checked
  - keep current hosted claim UX if `claim_required` is returned

## Registration And Claim State

The daemon remains authoritative for:

- handle-to-DID registration
- hosted claim state
- principal and vault ownership resolution

Filesystem identities can continue to persist client-local lifecycle status as a
performance optimization.

Env identities must not persist lifecycle metadata. Their claim and
registration state should be observed from daemon responses only.

Local mode requires no new claim-state behavior. The existing server ownership
flow already resolves all identities into the default local principal.

## Error Handling

The implementation should fail clearly in these cases:

- `AUTHSOME_IDENTITY_PRIVATE_KEY` is set without `AUTHSOME_IDENTITY`
- env private key is malformed hex
- env private key is not a valid Ed25519 32-byte raw private key
- env `handle + private_key` yields a DID that conflicts with the daemon's
  existing registration for that handle

Important invariant:

- the system must never silently rebind an existing handle to a new DID

## Security Notes

- Env-backed identities improve compatibility with sandboxed agents but move
  secret material into process environment variables.
- This is acceptable for the target use case, but the implementation should
  avoid logging raw private key values or echoing them in error messages.
- The design does not weaken daemon-side Proof-of-Possession validation because
  the DID is still derived from the signing key and validated against the
  handle-to-DID registry.

## Testing Plan

Add focused tests for:

- runtime identity resolution precedence
- full env mode using env-derived `handle + private_key + did`
- handle-only override mode loading or creating filesystem identity state
- fallback mode preserving current active filesystem identity behavior
- invalid partial env configuration
- malformed env private key errors
- env identity flow not writing metadata or updating `active_identity`
- filesystem identity flow preserving current metadata optimization
- bootstrap behavior for env identities re-checking daemon state instead of
  consulting local claim metadata

Regression tests should confirm existing filesystem workflows remain unchanged.

## Implementation Notes

Keep the change narrowly scoped:

- add a runtime identity resolver rather than scattering env checks throughout
  client code
- preserve existing public behavior for filesystem identities
- avoid server-side changes unless a current test reveals a mismatch in
  registration conflict handling

## Open Questions Resolved

- Env-backed identities are first-class, not sandbox-only.
- Full env mode uses `handle + private_key`; `did` is derived.
- Env identities are fully ephemeral on the client.
- Auto-registration remains enabled for env identities.
- Filesystem identities keep the current local metadata optimization.
- `AUTHSOME_IDENTITY` alone remains a local handle override, creating the named
  filesystem-backed identity when needed.
