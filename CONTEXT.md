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

`server/` owns `CredentialService` (`server/credential_service.py`) — the stateful coordinator that wires `auth/` flows with `vault/` storage and `audit/` logging. It is the only place where flows, storage, and audit are combined.

`CredentialService` is constructed per-request by the server with keyword-only `(credentials, providers, identity, principal_id, principal_role, vault_id)` and calls `auth/` flows to execute protocols, `vault/` (through the injected `CredentialRepository`) to persist results, and `audit/` to record events.

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

Think of this as the audit instrumentation layer. Defines what happened; `server/` decides where it goes.

**Owns:**
- `AuditEvent` domain model — mandatory fields: `identity`, `principal_id`, `provider`, `connection`; optional: `method`, `path`, `status`, `metadata`
- `log()` / `alog()` — emit an `AuditEvent` as an OTel `LogRecord` via `get_logger_provider()`
- Translation from `AuditEvent` → OTel `LogRecord`

**Does not own:**
- Storage — no file I/O, no database
- Provider lifecycle (`setup()` / `clear()` removed — owned by `server/`)
- Knowledge of where events are routed

**Imports:** `opentelemetry-api` only (no SDK, no storage). **Imports nothing from this codebase.** Imported by: `server/`, `proxy/`

---

### `server/` — Application orchestration and server-owned state

Think of this as the daemon process. Wires identity + auth + vault + audit together. Owns all server-side persistence.

**Owns:**
- `server/store/repositories.py` — all relational (SQLite/Postgres) registry implementations:
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
- `server/audit_store.py` — `SQLiteLogExporter` (OTel `LogExporter` impl) + `AuditStore` query interface; `LoggerProvider` lifecycle (setup at startup, shutdown at teardown)
- `server/routes/audit.py` — `GET /audit/events` (filtered, paginated admin read)
- `POST /audit/events` — ingest endpoint for proxy-side external AuditEvents; server enriches `principal_id` from PoP JWT

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
- Audit storage — ships External AuditEvents to server via `POST /audit/events` (fire-and-forget); does not call `audit.log()` directly

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

**Principal**: Non-cryptographic logical partition (human or team) that owns Vaults. Identified by an opaque **PrincipalId** (e.g., `principal_abc123def456`). Has no cryptographic key. Carries exactly one **PrincipalRole**.
_Avoid_: User, account, PrincipalHandle, profile

**PrincipalId**: Opaque stable identifier for a Principal. Never the email or handle — those can change; the PrincipalId cannot.
_Avoid_: principal_handle, principal_name, username

**PrincipalRole**: Authorization tier for a Principal. Either `admin` or `user`. The first Principal created on a server is always `admin`; all subsequent Principals are `user`. Stored as a column on the Principal record — not in environment variables or a separate table.
_Avoid_: permission level, access level, user type

**Vault**: Named credential store owned by exactly one Principal. Identified by an opaque **VaultId** (e.g., `vault_a1b2c3d4e5f6`). All credential store keys are prefixed `vault:<vault_id>:...`.
_Avoid_: credential store, token store, secret store, profile store

**VaultId**: Opaque stable identifier for a Vault. Used as the storage key segment. Stable across naming changes.
_Avoid_: vault_name, vault_handle

**VaultHandle**: Human-readable name for a Vault (e.g., `default`). Used in UIs and CLI; the VaultId is authoritative in storage.

**IdentityClaimRecord**: Binding from an Identity (Handle) to a Principal (PrincipalId) with a `ClaimStatus`. Created when an authenticated Principal confirms the browser claim that `authsome init` initiates. Vault access is gated until the claim is accepted.
_Avoid_: Claim, IdentityRegistration (as claim), join request

**ClaimStatus**: Lifecycle state: `pending` → `accepted` | `rejected`.

---

## Initialization & Claim Flow

There is a single flow for every deployment — no deployment mode (see ADR 0007). `authsome init` creates an Identity and registers it; the daemon returns `registration_status = "claim_required"` with a browser **claim URL**. The user opens the URL and registers (or logs in) with **email + password**: the first Principal created on a server becomes `admin`, all subsequent Principals are `user`. The authenticated Principal then confirms the claim, which binds the Identity to the Principal and creates the Principal's default Vault. Until the claim is `accepted`, all vault operations return `403`. The CLI opens the claim URL automatically and polls for completion (and prints the URL to stderr for headless use).

---

## Key Relationships

- An **Identity** is a cryptographic agent. It does not own credentials directly.
- An **Identity** claims a **Principal** via an **IdentityClaimRecord**. Claim must be `accepted` for vault access.
- A **Principal** owns one or more **Vaults** via **PrincipalVaultBindingRecords**. The server resolves the default Vault before constructing `CredentialService`.
- A **Vault** contains zero or more **Connections**, each scoped to one **Provider**.
- Multiple Identities may share one Vault by claiming the same Principal.
- A **ConnectionRecord** belongs to exactly one Vault. `vault:<vault_id>:...` is the key prefix.
- **ClientCredentials** are server-scoped — one `ProviderClientRecord` per Provider, shared across all Vaults.

---

## CredentialService Contract

`CredentialService` is a per-request credential lifecycle object constructed by the server:

```python
CredentialService(
    credentials=CredentialRepository(vault, identity=handle, principal_id=pid, vault_id=vid),
    providers=provider_repository,
    identity=handle,
    principal_id=pid,
    principal_role=role,
    vault_id=vid,
)
```

- `identity` — agent Handle, used for audit logging only
- `principal_id` — resolved by `OwnershipResolver` from the PoP JWT subject
- `principal_role` — the Principal's role (admin/user); gates provider-config and revoke operations
- `vault_id` — resolved from `PrincipalVaultBindingRegistry` by the server before constructing CredentialService
- `credentials` — a `CredentialRepository` over the encrypted KV store; CredentialService reads/writes only through this

CredentialService does not query registries, does not know about server filesystem paths, and does not build proxy route catalogs.

---

## Audit Contract

Every `AuditEvent` carries `identity` (the agent Handle) and `principal_id` (the PrincipalId). Both are required — every auditable action has an acting agent and an owning principal.

**External AuditEvent**: An event produced by the proxy layer — records an outbound HTTP call an agent made through the proxy to a third-party API (e.g., a call to `api.github.com`). Classified by provider and connection. Mandatory fields: identity, principal_id, provider, connection. Optional fields: HTTP method, path, response status.
_Avoid_: proxy event, API event, outbound event

**Internal AuditEvent**: An event produced by the server layer — records credential lifecycle operations (login, logout, token refresh, revocation) and auth flow steps.
_Avoid_: server event, auth event, lifecycle event

**Audit delivery**: External AuditEvents are shipped from the proxy to the server via `POST /audit/events` (fire-and-forget, best-effort). The proxy does not write to a local audit file. The server is the single source of truth for all audit events. `principal_id` is resolved server-side from the PoP JWT on the ingest request — the proxy does not need to supply it.

---

## Flagged Ambiguities

- **"PrincipalHandle"** — retired. The Principal is now identified by an opaque `PrincipalId`. Do not use PrincipalHandle in new code.
- **"VaultHandle"** — the human-readable display name. Do not use VaultHandle as a storage key; use VaultId.
- **"Claim"** — use `IdentityClaimRecord` for the binding object; use "claim" (lowercase) only as a verb.
- **"identity=server"** — retired. Previously a startup hack where the credential service was instantiated without a real identity; `CredentialService` is now built per-request in `routes/_deps.py`.
- **"credential"** — use **Connection** for the full authenticated session; use **access token** / **API key** for the individual secret.
