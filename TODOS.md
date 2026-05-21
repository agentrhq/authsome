# Module Separation TODOs

Goal: each module does exactly one thing. Types and helpers live in their module and are shared freely. Server-owned filesystem persistence lives only in `server/`. No module reaches across its boundary into another module's domain.

See `CONTEXT.md` for the target module responsibility map.

---

## A — Move server-owned registry implementations to `server/`

The registries in `identity/registry.py` and `identity/principal.py` are *server-owned persistence* — they write JSON files under `~/.authsome/server/`. They do not belong in the `identity/` module. The **data models** (types) stay in `identity/`; only the registry **classes** (filesystem I/O) move.

### A1. Create `server/registries.py`

Move these classes from `identity/` → `server/registries.py`:

- `IdentityRegistry` and `IdentityRegistrationError` from `identity/registry.py`
- `_JsonRegistry` base helper from `identity/principal.py`
- `PrincipalRegistry` from `identity/principal.py`
- `VaultRegistry` from `identity/principal.py`
- `IdentityClaimRegistry` from `identity/principal.py`
- `PrincipalVaultBindingRegistry` from `identity/principal.py`

These classes import domain models (`IdentityRegistration`, `PrincipalRecord`, etc.) from `identity/` — that is fine and should remain.

### A2. Update all registry import sites

Files that import registry classes and must be updated to import from `server/registries.py`:

- `server/dependencies.py` — imports all five registry classes
- `server/ownership.py` — imports `IdentityClaimRegistry`, `PrincipalRegistry`, `PrincipalVaultBindingRegistry`, `VaultRegistry`, `ClaimStatus`
- `server/identity_bootstrap.py` — imports `IdentityClaimRegistry` from `identity/principal.py` and `IdentityRegistry` from `identity/registry.py`
- `server/app.py` — imports `IdentityRegistry` from `identity/registry.py`

### A3. Gut the registry classes from `identity/`

After A2:

- `identity/registry.py` → keep `IdentityRegistration`, `IdentityRegistrationError`; delete `IdentityRegistry` class
- `identity/principal.py` → keep `ClaimStatus`, `PrincipalRecord`, `VaultRecord`, `IdentityClaimRecord`, `PrincipalVaultBindingRecord`; delete `_JsonRegistry`, `PrincipalRegistry`, `VaultRegistry`, `IdentityClaimRegistry`, `PrincipalVaultBindingRegistry`

### A4. Update `identity/__init__.py` exports if needed

Ensure nothing in the public `identity` API re-exports the moved registry classes.

---

## B — Fix `identity/local.py` → `cli/` circular dependency

`identity/local.py` imports `load_client_config` / `save_client_config` from `cli/client_config.py` inside `create_identity()` and `ensure_local_identity()`. The `identity/` module is a shared library module; it must not import from `cli/`.

### B1. Remove `create_identity()` side effect on client config

`create_identity()` currently calls `save_client_config(... active_identity=handle)`. Remove this.

Callers (`cli/main.py` `init` command) must be updated to call `save_client_config` themselves after `create_identity()` returns.

### B2. Remove `ensure_local_identity()` dependency on `load_client_config`

`ensure_local_identity()` reads `active_handle` from `load_client_config()` when `active_handle` is None. Change the function signature to accept `active_handle: str | None` as a parameter.

CLI callers pass the value they read from client config. `current_from_home()` in `identity/__init__.py` should be updated similarly.

### B3. Remove all `from authsome.cli.client_config import` from `identity/local.py`

After B1 + B2 there should be zero imports from `authsome.cli` anywhere in `identity/`.

---

## C — Remove `auth/service.py` reach into server internals

`auth/service.py` currently imports:
- `VaultRegistry` from `identity/principal.py` (server-owned registry)
- `get_server_home` from `authsome.paths` (server filesystem layout)

These are server concerns. `AuthService` should know only about `vault`, `identity`, `principal_id`, and `vault_id` that are passed to it.

### C1. Remove `_iter_registered_vault_ids()` from `AuthService`

This method queries `VaultRegistry` directly via `get_server_home` to iterate all vault IDs. This is a server-level operation.

Move the multi-vault iteration logic to `server/routes/connections.py` (the `revoke` route handler) or to a new helper in `server/`.

### C2. Update `AuthService.revoke()` signature

Change `revoke(self, provider: str)` to accept an optional `vault_ids: list[str] | None = None` parameter. When `vault_ids` is provided, iterate those. When None, iterate only `self._vault_id`.

The server route handler resolves the full vault list from `VaultRegistry` before calling `auth.revoke(provider, vault_ids=[...])`.

### C3. Remove server imports from `auth/service.py`

After C1 + C2, delete:
```python
from authsome.identity.principal import VaultRegistry
from authsome.paths import get_server_home
```

---

## D — Move proxy route catalog out of `AuthService`

`AuthService.proxy_routes()` and `AuthService._build_route_entry()` build the route catalog that the proxy uses to match requests. This is a server/proxy concern, not an auth concern.

### D1. Move `proxy_routes()` and `_build_route_entry()` to `server/`

Create `server/proxy_catalog.py` (or add to `server/routes/proxy.py`) with a standalone function:

```python
async def build_proxy_routes(auth: AuthService, scope: str) -> dict: ...
```

### D2. Update the proxy route endpoint

`server/routes/proxy.py` currently delegates to `auth.proxy_routes()`. Update it to call the new server-layer function.

### D3. Delete `proxy_routes()` and `_build_route_entry()` from `AuthService`

---

## E — Move `AuthService` from `auth/` to `server/` to make `auth/` a leaf

`AuthService` is not a flow implementation — it is a stateful coordinator that wires `auth/` flows with `vault/` storage and `audit/` logging. Its current home in `auth/` forces `auth/` to import `vault/` and `audit/`, making it non-leaf.

Moving it to `server/` makes all four domain modules (`identity/`, `auth/`, `vault/`, `audit/`) pure leaves with no intra-codebase imports.

### E1. Create `server/credential_service.py`

Move `AuthService` from `auth/service.py` to `server/credential_service.py`. Keep the class name `AuthService` for now to minimize diff noise; rename to `CredentialService` in a follow-up.

The moved class imports:
- `auth/` — flows, models, enums, sessions, provider resolution
- `vault/` — `Vault`
- `audit/` — `audit.alog()`

None of these are circular; all are lower-level leaves.

### E2. Update all import sites

Files that import `from authsome.auth import AuthService` or `from authsome.auth.service import AuthService` must be updated:

- `server/app.py`
- `server/routes/_deps.py`
- `server/routes/auth.py`
- `server/routes/connections.py`
- `server/routes/providers.py`
- `server/routes/proxy.py`
- `server/routes/ui.py`
- Any test fixtures that construct `AuthService`

Change all to `from authsome.server.credential_service import AuthService`.

### E3. Delete `auth/service.py`

After E2 there are no remaining imports. Delete the file.

### E4. Clean up `auth/__init__.py`

Remove the `AuthService` re-export if present. `auth/` now exports only flow classes and models.

### E5. Remove global `AuthService(identity="server")` from `server/app.py`

`server/app.py` lifespan creates `app.state.auth_service = AuthService(vault=..., identity="server")` — a single, identity-less instance used by routes that bypass PoP auth.

- Audit which routes call `get_auth_service(request)` instead of `get_protected_auth_service`
- Routes that need an identity → switch to `get_protected_auth_service`
- Routes that only need provider catalog → load bundled providers directly without an `AuthService`
- Delete `app.state.auth_service` from lifespan once no callers remain

---

## F — Remove `vault.home` from `Vault` class

`Vault.home` returns a filesystem path (`app_store.home`). This is used by:
- `auth/service.py` in `_iter_registered_vault_ids()` — removed in C1
- `server/routes/_deps.py` in `resolve_ui_request_identity()` to call `current_from_home(request.app.state.vault.home)`

### F1. Update `server/routes/_deps.py`

Replace `current_from_home(request.app.state.vault.home)` with `current_from_home(request.app.state.store.home)`. The store already exposes `.home`.

### F2. Audit remaining `vault.home` usages

Run `grep -rn "vault\.home"` and remove each remaining usage by threading the home path from `app.state.store.home` instead.

### F3. Remove `home` property from `Vault`

Once no callers remain, delete the property. Vault is a pure KV abstraction — it has no business knowing where it lives on disk.

---

## G — Make `audit/` injectable (optional, low priority)

`audit/__init__.py` uses module-level global state (`_log_path`, `_lock`). `audit.setup()` is called at server startup and `audit.clear()` at shutdown. This works, but makes the module stateful in a way that complicates testing.

### G1. (Optional) Replace global state with an `AuditLogger` object

Introduce an `AuditLogger` class with `log()` and `alog()` methods, constructed with a `Path`. Pass it to `AuthService` and any other callers rather than using module globals.

Keep the module-level `log()` / `alog()` functions as thin wrappers for backwards compatibility during transition.

---

## H — Terminology: align code with CONTEXT.md and UBIQUITOUS_LANGUAGE.md

The codebase still has pockets of old terminology.

### H1. Replace `IdentityRegistration.principal_handle` references

`CONTEXT.md` and `UBIQUITOUS_LANGUAGE.md` no longer use `principal_handle`. Check if any code still references this field or passes it as a key; update to `principal_id`.

### H2. Rename `ProviderMetadataRecord.identity` field

`ProviderMetadataRecord` carries an `identity` field (the handle). This was the old vault-scoping field. Verify it is now only used for audit context and rename or remove if redundant.

### H3. Purge `identity="server"` from tests and fixtures

After E3, grep for `identity="server"` in tests. Update fixtures to use a real handle or a test handle.

### H4. Update `CONTEXT.md` to reflect completed work

After each phase above completes, update the relevant section of `CONTEXT.md` to reflect actual module state.

---

## I — Documentation pass

### I1. Update `docs/refactor.md`

`docs/refactor.md` describes a storage-composition refactor. Prepend a section noting the module-separation work (this TODOS.md) must complete first, since it clarifies which code lives where before storage wiring is changed.

### I2. Update `CLAUDE.md` architecture table

The five-registry table in `CLAUDE.md` lists the registries under `identity/`. Update to reflect that the registry *implementations* now live in `server/registries.py`.

### I3. Confirm `UBIQUITOUS_LANGUAGE.md` registry definitions

After A1–A3, confirm the Identity Registry, PrincipalRegistry, VaultRegistry etc. entries in `docs/UBIQUITOUS_LANGUAGE.md` say "server-owned" and reference `server/registries.py`.

---

## Completion checklist

Before marking any phase done:

```bash
uv run pytest
uv run ruff check --fix src/ tests/
uv run ruff format src/ tests/
uv run ty check src/
uv run pre-commit run --all-files
```

No new test failures. No new type errors.

---

## Dependency order

```
A (move registries to server/)
B (fix identity/ → cli/ coupling)
    ↓
C (clean auth/service.py server imports)
D (move proxy_routes out of AuthService)
    ↓
E (move AuthService to server/credential_service.py — makes auth/ a leaf)
    ↓
F (remove vault.home)
G (optional: injectable audit)
H (terminology sweep)
I (docs pass)
```

A and B are independent and can run in parallel. C depends on A. D depends on C. E depends on C and D — auth/service.py must be clean before it moves. F depends on C. H and I depend on everything else completing.
