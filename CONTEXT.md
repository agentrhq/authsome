# authsome

authsome is the local auth layer for AI agents — it answers which agent, acting on behalf of whom, accessed what credential, and was that allowed.

## Module Responsibilities

Each module has one job. `identity/`, `auth/`, `vault/`, and `audit/` are **leaf modules** — they import nothing from this codebase and can be used and tested in isolation. `server/` is the only composition root.

```
identity/  ←─┐
auth/      ←─┤
vault/     ←─┤  server/  ←── cli/   (via HTTP, not Python import)
audit/     ←─┘            ←── proxy/ (via HTTP, not Python import)
```

---

### `identity/` — Cryptographic identity primitives

Think of this as the OpenID Connect layer. Handles key material, DIDs, and proof-of-possession tokens.

**Owns:**
- Ed25519 key pair generation and serialization (`local.py`)
- `did:key` DID derivation from public keys (`local.py`)
- `IdentityMetadata` model — client-side cached state for a local identity
- `IdentityRegistration` model — the server's record of a registered handle/DID binding
- PoP JWT creation and validation (`proof.py`)
- `ClaimStatus`, `PrincipalRecord`, `VaultRecord`, `IdentityClaimRecord`, `PrincipalVaultBindingRecord` — shared domain models

**Does not own:**
- Filesystem-backed registries (those are server state, not identity primitives)
- Client config management (that is `cli/` territory)
- Principal/vault lifecycle decisions (that is `server/` territory)

**Imports nothing from this codebase.** Used by: `server/`, `cli/`

---

### `auth/` — OAuth and API key flow implementations

Think of this as the OAuth 2.0 protocol library. Each flow takes provider config and credentials in, returns tokens out. No storage, no audit, no identity imports.

**Owns:**
- OAuth 2.0 flows: PKCE, Device Code, DCR+PKCE (`flows/`)
- API key collection flow (`flows/api_key.py`)
- Flow base class and token refresh logic
- Provider models: `ProviderDefinition`, `OAuthConfig`, `ApiKeyConfig`, bundled provider JSON
- Credential models: `ConnectionRecord`, `ProviderClientRecord`, `ProviderMetadataRecord`, `ProviderStateRecord`
- `AuthSession` — transient flow session state

**Does not own:**
- Credential persistence (that is `vault/` + `server/` territory)
- Audit logging (that is `audit/` + `server/` territory)
- Proxy route catalog building
- Server registry reads

**Imports nothing from this codebase.** Used by: `server/`

---

### `server/` — CredentialService and application orchestration

`server/` owns `CredentialService` (currently called `AuthService`) — the stateful coordinator that wires `auth/` flows with `vault/` storage and `audit/` logging. It is the only place where flows, storage, and audit are combined.

`CredentialService` is constructed per-request by the server with `(vault, identity, principal_id, vault_id)` and calls `auth/` flows to execute protocols, `vault/` to persist results, and `audit/` to record events.

> Current state: `AuthService` lives in `auth/` and imports `vault/` and `audit/` directly. Moving it to `server/` (TODOS phase E) makes `auth/` a true leaf.

---

### `vault/` — Encrypted credential storage

Think of this as the secrets layer. Encrypts and decrypts credential blobs transparently.

**Owns:**
- `Vault` — AES-256-GCM encrypted KV wrapper over `AsyncKeyValue`
- `VaultCrypto` — key management (local file, OS keyring)
- Encrypted get/put/delete/list over named collections

**Does not own:**
- Server filesystem layout or path resolution
- Registry lookups
- Business logic about which vault belongs to which principal

**Imports nothing from this codebase.** Imported by: `auth/`, `server/`

---

### `audit/` — Structured event recording

Think of this as the append-only ledger. Records who did what and when.

**Owns:**
- `AuditEvent` model
- `log()` / `alog()` — append to a structured JSON-lines log file
- `setup()` / `clear()` — log file lifecycle (called by server at startup/shutdown)

**Does not own:**
- Business logic
- Any storage beyond the append-only log file

**Imports nothing from this codebase.** Imported by: `auth/`, `server/`

---

### `server/` — Application orchestration and server-owned state

Think of this as the daemon process. Wires identity + auth + vault + audit together. Owns all server-side persistence.

**Owns:**
- `server/registries.py` — all filesystem-backed registry implementations:
  - `IdentityRegistry` (handle → DID)
  - `PrincipalRegistry` (principal_id → email)
  - `VaultRegistry` (vault_id → handle)
  - `IdentityClaimRegistry` (identity → principal + ClaimStatus)
  - `PrincipalVaultBindingRegistry` (principal → default vault)
- `server/ownership.py` — `OwnershipResolver` (local and hosted variants), `ResolvedOwnership`
- `server/identity_bootstrap.py` — deployment-specific identity registration behavior
- `server/dependencies.py` — infrastructure wiring (paths, store, vault, config)
- `server/app.py` — FastAPI application factory and lifespan
- `server/routes/` — HTTP API surface
- `server/schemas.py` — API response schemas

**All filesystem interaction for server-owned state lives here.** No other module writes to server-owned paths.

**Imported by:** nothing (top of the import graph)

---

### `proxy/` — Credential injection proxy

A mitmproxy-based HTTPS proxy. Intercepts outgoing agent requests and injects auth headers.

**Owns:**
- `proxy/server.py` — mitmproxy addon that intercepts requests
- `proxy/runner.py` — background thread lifecycle
- `proxy/router.py` — `RouteMatch` / `RouteResolution` types
- `proxy/certs.py` — CA certificate management

**Does not own:**
- Credential loading (asks the server)
- Route catalog construction (asks the server)
- Provider definitions

**Imported by:** `cli/`

---

### `cli/` — Client to the daemon

Click-based CLI and HTTP client. Everything here is a client to the server HTTP API.

**Owns:**
- `cli/main.py` — Click command tree
- `cli/client.py` — `RuntimeClient` (async HTTP client for daemon requests, attaches PoP JWT)
- `cli/client_config.py` — client-owned config (`active_identity`, `vault_id`, proxy settings)
- `cli/context.py` — `CliRuntime` wiring container
- `cli/daemon_control.py` — start/stop the daemon process

**Does not own:**
- Server registry operations
- Direct vault or store access
- Identity key generation (delegates to `identity/`, result stored by CLI via `identity/local.py`)

**Imported by:** nothing (entry point)

---

## Domain Language

### Identity & Authentication

**Identity**: The cryptographic agent — Ed25519 key pair, `did:key` DID, and human-readable Handle. Created locally; registered with the daemon. Is not a credential namespace.

**Handle**: Human-readable name for an Identity (e.g., `brisk-boldly-clearly-1234`). Used as `sub` in PoP JWTs.

**DID**: `did:key` Ed25519 identifier derived from the Identity's public key. Used as `iss` in PoP JWTs.

**PoP JWT**: Short-lived (60 s) Proof-of-Possession token signed with the Identity's Ed25519 private key. Bound to `htm`, `htu`, `body_sha256`. Sent as `Authorization: PoP <token>`.

**Principal**: Non-cryptographic logical partition (human or team) that owns Vaults. Identified by an opaque **PrincipalId** (e.g., `principal_abc123def456`). Has no cryptographic key.
_Avoid_: User, account, PrincipalHandle, profile

**PrincipalId**: Opaque stable identifier for a Principal. Never the email or handle — those can change; the PrincipalId cannot.
_Avoid_: principal_handle, principal_name, username

**Vault**: Named credential store owned by exactly one Principal. Identified by an opaque **VaultId** (e.g., `vault_a1b2c3d4e5f6`). All credential store keys are prefixed `vault:<vault_id>:...`.
_Avoid_: credential store, token store, secret store, profile store

**VaultId**: Opaque stable identifier for a Vault. Used as the storage key segment. Stable across naming changes.
_Avoid_: vault_name, vault_handle

**VaultHandle**: Human-readable name for a Vault (e.g., `default`). Used in UIs and CLI; the VaultId is authoritative in storage.

**IdentityClaimRecord**: Binding from an Identity (Handle) to a Principal (PrincipalId) with a `ClaimStatus`. Created during `authsome init --email`. Vault access is gated until the claim is accepted.
_Avoid_: Claim, IdentityRegistration (as claim), join request

**ClaimStatus**: Lifecycle state: `pending` → `accepted` | `rejected`.

---

## Initialization & Claim Flow

**Local mode**: `authsome init` creates an Identity, auto-accepts its claim under the implicit local Principal, and creates the default Vault. No email required.

**Hosted mode**: `authsome init --email manoj@example.com` creates an Identity, creates or finds the Principal by email, and registers an `IdentityClaimRecord` with `claim_status = pending`. A human reviews the claim in the UI and accepts or rejects it. All vault operations return `403` until the claim is accepted.

---

## Key Relationships

- An **Identity** is a cryptographic agent. It does not own credentials directly.
- An **Identity** claims a **Principal** via an **IdentityClaimRecord**. Claim must be `accepted` for vault access.
- A **Principal** owns one or more **Vaults** via **PrincipalVaultBindingRecords**. The server resolves the default Vault before constructing `AuthService`.
- A **Vault** contains zero or more **Connections**, each scoped to one **Provider**.
- Multiple Identities may share one Vault by claiming the same Principal.
- A **ConnectionRecord** belongs to exactly one Vault. `vault:<vault_id>:...` is the key prefix.
- **ClientCredentials** are server-scoped — one `ProviderClientRecord` per Provider, shared across all Vaults.

---

## AuthService Contract

`AuthService` is a per-request credential lifecycle object constructed by the server:

```python
AuthService(vault=vault, identity=handle, principal_id=pid, vault_id=vid, deployment_mode=mode)
```

- `identity` — agent Handle, used for audit logging only
- `principal_id` — resolved by `OwnershipResolver` from the PoP JWT subject
- `vault_id` — resolved from `PrincipalVaultBindingRegistry` by the server before constructing AuthService
- `vault` — the encrypted KV store; AuthService reads/writes only through this

AuthService does not query registries, does not know about server filesystem paths, and does not build proxy route catalogs.

---

## Audit Contract

Every `AuditEvent` carries `identity` (the agent Handle) and `principal_id` (the PrincipalId). Both are required — every auditable action has an acting agent and an owning principal.

---

## Flagged Ambiguities

- **"PrincipalHandle"** — retired. The Principal is now identified by an opaque `PrincipalId`. Do not use PrincipalHandle in new code.
- **"VaultHandle"** — the human-readable display name. Do not use VaultHandle as a storage key; use VaultId.
- **"Claim"** — use `IdentityClaimRecord` for the binding object; use "claim" (lowercase) only as a verb.
- **"identity=server"** — a temporary hack in `app.py` where `AuthService` is instantiated at startup without a real identity. This is a known violation to be removed.
- **"credential"** — use **Connection** for the full authenticated session; use **access token** / **API key** for the individual secret.
