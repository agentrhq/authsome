# Storage, Secrets, Identity, And Composition Refactor Plan

_Updated 2026-05-27. Reflects actual codebase state vs. original plan._

---

## What shipped (original plan phases 1–8)

| Original Phase | Status | Notes |
|---|---|---|
| 1 — Storage foundation | **Replaced** | `StoreDatabase` (SQLite/Postgres) for registries; `DiskStore + AesGcmEncryptionWrapper` for credentials. Two-store design is better than the single-KV-substrate plan. |
| 2 — Secret source chain | **Partial** | `ServerSecretResolver` (env → file → keyring → generate) covers server-owned keys (master key, UI session key). Client identity private keys still resolved in `identity/local.py`. |
| 3 — IdentityRepository | **Partial** | Server-side: `IdentityRegistry` in `server/store/repositories.py` (relational, done). Client-side: still raw `identity/local.py`, no structural server boundary. |
| 4 — CredentialRepository | **Not done** | `AuthService` still calls `build_store_key()` and `self._vault.get/put/delete` directly. This is the most significant remaining gap. |
| 5 — ProviderRepository | **Partial** | `ProviderDefinitionRepository` handles custom providers (done). Bundled provider loading still lives in `AuthService._load_bundled_providers()`. |
| 6 — Slim AuthService | **Partial** | Receives `ProviderDefinitionRepository` (done). Still owns raw vault key construction and all vault I/O. |
| 7 — Server composition root | **Functional** | `ServerStore` + `app.state` + `dependencies.py` cover the spirit. No `ServerState` dataclass. `identity="server"` placeholder is gone. |
| 8 — Proxy server authority | **Done** | `proxy_catalog.py` + `/proxy/routes` endpoint. |
| 9 — Docs | **Partial** | CONTEXT.md and UBIQUITOUS_LANGUAGE.md updated. |

### What also landed (not in the original plan)

- `DekManager` with Argon2id KDF — stronger key derivation than originally specced
- `OwnershipResolver` (Local + Hosted) — resolves principal/vault from an identity handle
- `IdentityBootstrapService` (Local + Hosted) — handles claim-and-accept flow at registration time
- `HostedAccountService` — email/password hosted auth, session JWT management
- `UiSessionStore` + browser session cookie — browser-based UI auth separate from PoP
- `ownership_cache` — short-circuits repeat registry lookups per request

---

## Remaining work

Three gaps remain. They are listed in delivery order — each one unblocks the next.

---

### Phase A — CredentialRepository

**The gap:** `AuthService` is both the credential lifecycle coordinator and the credential storage layer. It manually constructs all vault keys (`vault:<vault_id>:<provider>:connection:<name>`, `server:<provider>:client`) using `build_store_key()` and calls `self._vault.get/put/delete` directly across ~15 methods. Key construction is scattered, not tested independently, and makes `AuthService` impossible to test without a real Vault.

**What to build:**

```python
class CredentialRepository:
    def __init__(self, vault: Vault, vault_id: str) -> None: ...

    # Connection records (vault-scoped)
    async def get_connection(self, provider: str, connection: str) -> ConnectionRecord | None: ...
    async def save_connection(self, record: ConnectionRecord) -> None: ...
    async def delete_connection(self, provider: str, connection: str) -> None: ...
    async def list_connection_keys(self) -> list[str]: ...  # returns raw keys for list_connections

    # Provider metadata (vault-scoped)
    async def get_provider_metadata(self, provider: str) -> ProviderMetadataRecord | None: ...
    async def save_provider_metadata(self, record: ProviderMetadataRecord) -> None: ...
    async def delete_provider_metadata(self, provider: str) -> None: ...

    # Provider state (vault-scoped)
    async def get_provider_state(self, provider: str) -> ProviderStateRecord | None: ...
    async def save_provider_state(self, record: ProviderStateRecord) -> None: ...

    # Provider client credentials (server-scoped, shared across vaults)
    async def get_provider_client(self, provider: str) -> ProviderClientRecord | None: ...
    async def save_provider_client(self, record: ProviderClientRecord) -> None: ...
    async def delete_provider_client(self, provider: str) -> None: ...
```

`CredentialRepository` owns all key construction. No raw `build_store_key()` calls outside it.

**Where it lives:** `server/credential_repository.py`. It is server-owned because it knows about `vault_id` scoping. `auth/` remains a leaf.

**Updated `AuthService` signature:**

```python
AuthService(
    credentials: CredentialRepository,
    providers: ProviderRepository,        # see Phase B
    identity: str | None,
    principal_id: str | None,
    vault_id: str | None,
    deployment_mode: str,
)
```

`AuthService` no longer receives `vault` directly. All vault I/O goes through `credentials`.

**Required tests:**
- Connection record save/load/delete roundtrips through encrypted vault
- Provider metadata, state, and client records are vault-scoped vs server-scoped correctly
- Key construction is encapsulated — callers never construct raw keys
- `AuthService` tests use a stub `CredentialRepository`; no real vault needed

---

### Phase B — Unified ProviderRepository

**The gap:** `ProviderDefinitionRepository` handles custom providers (relational). Bundled providers are loaded in `AuthService._load_bundled_providers()` on every construction. The two sources are merged inside `AuthService.list_providers()` / `get_provider()`, mixing orchestration with provider resolution.

**What to build:**

Extend `ProviderDefinitionRepository` to unify both sources:

```python
class ProviderRepository:
    def __init__(self, db_repo: ProviderDefinitionRepository) -> None: ...

    async def get(self, name: str) -> ProviderDefinition: ...          # custom overrides bundled
    async def list(self) -> list[ProviderDefinition]: ...              # merged, sorted
    async def list_by_source(self) -> dict[str, list[...]]: ...        # {"bundled": [...], "custom": [...]}
    async def save_custom(self, definition: ProviderDefinition, *, force: bool = False) -> None: ...
    async def delete_custom(self, name: str) -> bool: ...
    async def is_custom(self, name: str) -> bool: ...
```

Bundled provider loading moves here (called once, cached on the instance). `AuthService` no longer loads bundled providers.

**Required tests:**
- Custom provider overrides bundled provider with the same name
- Bundled provider is returned when no custom exists
- `is_custom()` returns True only for custom definitions

---

### Phase C — Roles and Route Authorization

**The gap:** The current admin check (`is_admin_principal()` in `credential_service.py`) reads `AUTHSOME_ADMIN_PRINCIPALS` env on every call — no persisted roles, no typed role model, no per-route enforcement. The existing `IdentityClaimRecord` has no role field. There is no structural separation between user-scoped and admin-scoped API routes.

This phase is needed by the product roadmap items: **roles & admin routes**, **policy layer**, and **multi-user proper operation**.

**What to build:**

**Step 1 — Add role to `IdentityClaimRecord`:**

```python
class PrincipalRole(str, Enum):
    USER = "user"
    ADMIN = "admin"

class IdentityClaimRecord(BaseModel):
    ...
    role: PrincipalRole = PrincipalRole.USER
```

Schema migration: add `role TEXT NOT NULL DEFAULT 'user'` to `identity_claims`. Env-listed admin principals auto-promote to `admin` on claim accept (backwards compatible).

**Step 2 — Role-aware `ResolvedOwnership`:**

```python
@dataclass(frozen=True)
class ResolvedOwnership:
    identity: str
    principal_id: str
    vault_id: str
    role: PrincipalRole
```

`OwnershipResolver.resolve()` returns the role from the claim. `is_admin_principal()` is removed from `credential_service.py`.

**Step 3 — FastAPI route dependencies:**

```python
# server/routes/_deps.py
async def require_admin(request: Request) -> ResolvedOwnership:
    ownership = request.state.ownership  # set by get_protected_auth_service
    if ownership.role != PrincipalRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin role required")
    return ownership
```

Admin-only routes (provider client mutation, custom provider registration, vault rekey, identity management) declare `Depends(require_admin)`. User routes declare `Depends(get_protected_auth_service)`.

**Step 4 — Admin route prefix:**

Move admin-only routes to `/admin/` prefix. Non-admin routes stay at current paths. No user-visible behavior change for existing local installs (LocalOwnershipResolver auto-assigns the single local principal as admin).

**Required tests:**
- `OwnershipResolver.resolve()` returns correct role from claim
- Non-admin principal cannot call admin routes (403)
- Admin principal can call admin routes
- Env-listed principals auto-promote to admin at claim time
- Local (single-user) installs: the implicit principal is always admin
- Hosted installs: first registered principal defaults to admin; subsequent default to user

---

### Phase D — Injectable `AuditLogger` with OTel hooks

**The gap:** `audit/__init__.py` is module-level mutable global state — `_log_path` and `_lock` are set by `setup()` / `clear()`. `alog()` is a synchronous alias for `log()` in an async wrapper. The module-level design causes test bleed (there is already shim code to isolate analytics tests). `AuditEvent` carries `identity` but not `principal_id`, despite ADR-0003 requiring both on every event. The one real audit call is buried inside `AuthService._get_oauth_token()` — a private refresh helper — rather than at the method boundary where the orchestrator can see it.

**Deletion test.** Delete `audit/` and inline the file write in `_get_oauth_token()`. Complexity barely moves — the module is currently a pass-through. But the seam is in exactly the right position to become the single choke point for all observability: one change to `AuditLogger.emit()` could add OTel spans, Prometheus counters, or a webhook across the entire credential lifecycle. That leverage is the target.

**What to build:**

```python
class AuditLogger:
    def __init__(self, log_path: Path) -> None: ...

    def emit(self, event_type: str, *, identity: str | None, principal_id: str | None, **kwargs: Any) -> None:
        """Write a structured JSON-lines entry and push an OTel span."""
```

- `principal_id` is a required parameter (not optional) — enforces ADR-0003.
- `emit()` writes the JSON line synchronously (same as today) and calls `tracer.start_as_current_span()` from the OTel SDK. When no OTel exporter is configured, this is a no-op.
- `log()` / `alog()` module-level globals are removed. `setup()` / `clear()` are removed.
- `AuditLogger` is instantiated once in `app.py` lifespan and stored in `app.state.audit_logger`.
- `AuthService` receives `audit_logger: AuditLogger` at construction and calls `audit_logger.emit()` at method boundaries (begin/resume/logout/refresh), not inside private helpers.

**Updated `AuthService` signature (combined with Phase A):**

```python
AuthService(
    credentials: CredentialRepository,
    providers: ProviderRepository,
    audit_logger: AuditLogger,
    identity: str | None,
    principal_id: str | None,
    vault_id: str | None,
    deployment_mode: str,
)
```

**Required tests:**
- `AuditLogger.emit()` writes a JSON-lines record with both `identity` and `principal_id` fields
- Emitting without `principal_id` raises at call time (not silently drops the field)
- `AuthService` tests pass a stub `AuditLogger`; no filesystem needed
- No module-level state: two `AuditLogger` instances in the same test do not interfere

---

### Phase E — Split `identity/local.py` into pure crypto and `ClientIdentityStore`

**The gap:** `identity/local.py` does three unrelated things that cannot be tested independently:

1. **Pure crypto** — `public_key_to_did_key`, `public_key_from_did_key`, `private_key_to_hex`, `private_key_from_hex`, `generate_handle`, `validate_handle`. No I/O, no state.
2. **Filesystem I/O** — `create_identity`, `load_identity`, `mark_registered`, `mark_claimed`, `ensure_local_identity`, path helpers. Reads/writes `~/.authsome/client/identities/`.
3. **Client config coupling** — `_read_active_identity_handle`, `_write_active_identity_handle`. Reads/writes `~/.authsome/client/config.json`.

CONTEXT.md declares `identity/` a stateless leaf. Two `TODO` comments in `local.py` confirm the intent: "Storage of identities should be server property. The identities module should be stateless." The filesystem and config coupling mean testing the pure crypto functions requires a `tmp_path` fixture.

**Deletion test.** Delete the filesystem and config functions from `identity/local.py`. They reappear in a new `ClientIdentityStore` in `cli/`. The pure crypto functions have no natural home except `identity/` — they stay, and become fully unit-testable.

**What to build:**

Keep in `identity/local.py` (pure functions only):
- `public_key_to_did_key`, `public_key_from_did_key`
- `private_key_to_hex`, `private_key_from_hex`
- `generate_handle`, `validate_handle`
- `IdentityMetadata`, `RuntimeIdentity`, `IdentityStatus`, `IdentitySource` models

Move to `cli/identity_store.py` as a `ClientIdentityStore` class:
- `identities_dir`, `identity_key_path`, `identity_metadata_path`
- `create_identity`, `load_identity`, `load_private_key`, `identity_exists`
- `mark_registered`, `mark_claimed`, `ensure_local_identity`
- `_read_active_identity_handle`, `_write_active_identity_handle`
- `load_runtime_identity` (reads from env or delegates to `ClientIdentityStore`)

`ClientIdentityStore.__init__(home: Path)` takes the root home directory. It does not import from `server/`.

**Required tests:**
- All `identity/` tests are pure unit tests — no `tmp_path`, no monkeypatching of filesystem
- `ClientIdentityStore` tests use `tmp_path`; no crypto setup needed beyond a fixed test key
- `load_runtime_identity` from env uses only pure functions — no `ClientIdentityStore` instantiated

---

### Phase F — Move `ReplayCache` from `identity/` to `server/`

**The gap:** `ReplayCache` in `identity/proof.py` is mutable server-owned state: it lives in `app.state.proof_replay_cache`, grows unboundedly between TTL sweeps, and its lifecycle (creation at startup, reset for tests) is a `server/` concern. `identity/` is declared a stateless leaf; a TTL-eviction cache with per-process scope is the opposite of stateless.

The seam already exists: `validate_proof_jwt()` accepts `replay_cache: ReplayCache | None` as a parameter — the function is pure, the cache is injected. Only the type needs to move.

**What to build:**

Move `ReplayCache` to `server/replay_cache.py`. `identity/proof.py` becomes a file of pure functions — create a PoP JWT, validate a PoP JWT — with no mutable state and no lifecycle concerns. `validate_proof_jwt()` retains its current signature; `_deps.py` imports `ReplayCache` from its new location.

No behavior changes. No interface changes. Just a file move.

**Required tests:**
- `identity/proof.py` tests require no server state setup
- `ReplayCache` TTL eviction tested in `server/` where its lifecycle is owned

---

### Phase G — Narrow `proxy_catalog.py` seam from `AuthService` to a data transfer

**The gap:** `build_proxy_routes(auth: AuthService)` takes the full `AuthService` to extract two things: connected provider names with their default connections (`auth.list_connections()`) and provider definitions (`auth.get_provider()`). The function cannot be tested without a vault-backed `AuthService`. It is effectively a view over `AuthService`, not a module with independent depth.

**What to build:**

Introduce a `ProxyRouteInput` data class:

```python
@dataclass(frozen=True)
class ProxyRouteInput:
    provider_name: str
    connection_name: str
    api_url: str | list[str] | None
    auth_endpoint_paths: list[str]
```

The `/proxy/routes` route handler resolves this list from `AuthService` before calling the catalog. `build_proxy_routes()` becomes:

```python
def build_proxy_routes(inputs: list[ProxyRouteInput]) -> dict: ...
```

A pure function. No `AuthService` import in `proxy_catalog.py`. No vault, no sessions, no database needed to test proxy route-building.

**Required tests:**
- Route deduplication, URL normalization, and regex route ordering are unit-testable with fabricated `ProxyRouteInput` lists
- Ambiguous URL handling tested without constructing vault state
- Empty connection list returns empty routes

---

## Non-goals (unchanged from original plan)

- Do not implement a hosted product mode (already done separately)
- Do not implement PostgreSQL deployment documentation in this slice
- Do not add network policy modes to proxy in this slice
- Do not encrypt logical storage keys
- Do not create inheritance hierarchies for stores or repositories

---

## Verification commands

Run before claiming any phase done:

```bash
uv run pytest
uv run ruff check src/ tests/
uv run ty check src/
uv run pre-commit run --all-files
```
