# ADR 0002: Server-Registered Identities

## Status

Accepted.

## Context

Authsome previously treated a local `default` profile as the implicit acting identity. That made protected daemon requests rely on client-side profile state and allowed a valid PoP signature to choose any `sub` value without a daemon-owned registry check.

## Decision

The daemon registry is authoritative for identity handles. A protected request is accepted only when:

- the PoP JWT signature validates against `iss`;
- `iss` is the cryptographic identity DID;
- `sub` is a human-readable handle registered with the daemon;
- the daemon registry maps that `sub` to the same DID as `iss`.

The CLI bootstraps a non-default human-readable handle and Ed25519 `did:key`, registers the pair with the daemon, and then uses that identity for protected requests. `default` remains only the conventional connection name.

Storage ownership is path-based:

- `~/.authsome/identities/<handle>.key` is CLI-owned private key material.
- `~/.authsome/identities/<handle>.json` is a CLI-owned identity metadata cache (`registered: bool`, `did`, `created_at`).
- `~/.authsome/server/identity_registry.json` is daemon-owned and authoritative.
- `~/.authsome/server/master.key`, `~/.authsome/server/kv_store/`, and `~/.authsome/server/daemon/` are daemon-owned.
- `GlobalConfig` (including `active_identity`) is stored in the KV store at `~/.authsome/server/kv_store/` under `config/global`, not as a flat JSON file.

## Consequences

This is a breaking change. There is no implicit `default` profile or identity. Existing credentials under old `profile:default:*` keys are not migrated in this release and may be inaccessible until a later import or migration tool exists. Users with old installs must run `authsome init` again to create and register a fresh identity.

Registration is idempotent only for the same handle and DID. Handle collisions and DID collisions are rejected.

`POST /identities/register` is unauthenticated by design — a PoP JWT requires a registered identity, so registration must precede authentication. Any local process that can reach the daemon socket may register a handle/DID pair. This is acceptable for a local daemon where the file system already gates access to `~/.authsome/`. A bootstrap token scheme was considered and deferred; there is no current threat model that justifies the added complexity.
