# Storage, Secrets, Identity, And Composition Refactor Plan

## Summary

Refactor authsome around the design settled in discussion:

- Use `py-key-value-aio`'s `AsyncKeyValue` as the only low-level storage interface.
- Use composition over inheritance.
- Use `DiskStore` locally and keep PostgreSQL possible later without adding remote mode now.
- Separate **storage substrate** from **storage namespace**.
- Use `AesGcmEncryptionWrapper` (AES-256-GCM) for encrypted credential records.
- Resolve master keys and identity signing keys through the same `SecretSource` chain: env, keyring, local fallback.
- Keep client Identity private keys out of server storage permanently.
- Keep product surface unchanged: no migration command, no remote feature launch, no new user workflow.
- This is a new product — no data migration is needed or planned.

This plan is intended as a future implementation document. No code should be changed immediately.

## Settled Design Rules

1. **Composition over inheritance**
   - Prefer composed collaborators with explicit dependencies.
   - Avoid class hierarchies for storage, identity, auth, and server orchestration.
   - Use protocols only where they describe an external seam or enable tests.

2. **`AsyncKeyValue` is the storage seam**
   - Do not introduce a custom `RecordStore`.
   - Use `key_value.aio.protocols.key_value.AsyncKeyValue` directly.
   - Domain code should depend on repositories, not raw stores.

3. **Shared substrate is not shared ownership**
   - Local mode may use one physical `DiskStore`.
   - Client and Server must use separate namespaced store wrappers.
   - Never say "shared storage" without qualifying it as "shared substrate, separate namespaces."

4. **Client signing keys are client-only**
   - Remote server storage must never contain client Identity private keys.
   - Server stores only public registration data: `handle`, `did`, timestamps.
   - Client owns `active_identity`, local metadata, and signing private key material.

5. **No product surface expansion**
   - Do not add remote mode as a user-facing feature.
   - Do not add migration support in this slice.
   - Do not add new commands unless required to preserve current behavior.
   - Use the refactor to simplify internal seams only.

## Target Architecture

### Client vs Server Split

Every module, namespace, and repository belongs to one side. Use this as the organizing principle throughout code and docs.

**Client side** — what the agent or human runs locally:
- Holds the Ed25519 identity and private signing key.
- Signs PoP JWTs.
- Calls the server via `RuntimeClient`.
- CLI and UI are its interfaces.
- Owns `client/*` namespace in storage.

**Server side** — the daemon process:
- Holds the identity registry (handle → DID).
- Holds the credential vault.
- Runs the proxy.
- Owns provider lifecycle.
- Owns `server/*` and `vault/*` namespaces in storage.

When describing a module, repository, or method, always state which side owns it.

### Storage Terms

Use these terms consistently in docs and code comments:

- **StorageSubstrate**
  - The concrete `AsyncKeyValue` backend.
  - Examples: `DiskStore`, `PostgreSQLStore`, `MemoryStore`.

- **StorageNamespace**
  - A prefixed collection/key space over a substrate.
  - Examples: `client/*`, `server/*`, `vault/*`.

- **SecretSource**
  - A source for sensitive root/signing material.
  - Examples: environment, OS keyring, local fallback.

- **Repository**
  - A domain API over a namespaced `AsyncKeyValue` store.
  - Owns key naming, serialization, validation, and invariants.

### Local Mode Wiring

Use one local substrate:

```python
raw_store = DiskStore(directory=home / "server" / "kv_store")
```

Compose namespaced stores:

```python
client_store = PrefixCollectionsWrapper(raw_store, prefix="client")
server_store = PrefixCollectionsWrapper(raw_store, prefix="server")
vault_base_store = PrefixCollectionsWrapper(raw_store, prefix="vault")
```

Create encrypted credential store:

```python
vault_store = AesGcmEncryptionWrapper(vault_base_store, key=master_key)
```

Repositories receive stores:

```python
identity_repo = IdentityRepository(client_store, secret_resolver)
identity_registry = IdentityRepository(server_store, secret_resolver=None)
credential_repo = CredentialRepository(vault_store)
provider_repo = ProviderRepository(server_store)
```

### Future Remote Wiring

Do not implement as product behavior now, but ensure the composition can support this later:

```python
client_raw = DiskStore(directory=home / "client" / "kv_store")
server_raw = PostgreSQLStore(url=database_url, table_name="authsome_kv")
```

Then:

```python
client_store = PrefixCollectionsWrapper(client_raw, prefix="client")
server_store = PrefixCollectionsWrapper(server_raw, prefix="server")
vault_store = AesGcmEncryptionWrapper(
    PrefixCollectionsWrapper(server_raw, prefix="vault"),
    key=master_key,
)
```

Client signing keys still resolve only from client-side `SecretSource` instances.

## Module Responsibilities

### Identity

**Belongs to: client side**

Identity owns:

- Ed25519 keypair creation.
- DID derivation from public key.
- DID public-key parsing.
- PoP JWT signing.
- PoP JWT validation.
- Identity metadata model helpers.
- Identity registration model helpers.

Identity must not own:

- OAuth flows.
- Credential refresh.
- Provider registry.
- Proxy routing.
- Vault encryption policy.
- Server authorization policy.

### Auth

**Belongs to: server side** (AuthService runs in the daemon; flows are server-initiated)

Auth owns:

- Provider authentication flows.
- PKCE flow.
- Device Code flow.
- DCR + PKCE flow.
- API key collection and validation.
- Credential refresh.
- Logout/revoke lifecycle behavior.
- Constructing provider auth headers from valid connection records.

Auth must not own:

- Client identity file/key loading.
- PoP JWT validation.
- Identity registry authority.
- Server policy.
- Storage substrate creation.
- Proxy route authority.

### Storage/Vault

**Belongs to: server side**

Storage owns:

- Store factories.
- `AsyncKeyValue` composition.
- Prefix wrappers.
- AES-256-GCM encrypted store construction (`AesGcmEncryptionWrapper`).
- Secret source construction for encryption key material.

Vault should become a narrow composition concept, not a parallel store API.

`AesGcmEncryptionWrapper` is the only encrypted wrapper. Do not add a second one.

### Server

**Belongs to: server side** — composition root

Server owns orchestration:

- Validate protected requests.
- Verify PoP signature.
- Check `sub -> DID` against server-owned registry.
- Create per-identity Auth collaborators.
- Call Auth for provider lifecycle.
- Call repositories for persistence.
- Append audit events to `~/.authsome/server/audit.log` (one JSON object per line).
- Apply local/hosted policy.

Server is the composition root.

### Proxy

**Belongs to: server side**

Proxy owns:

- Receiving outbound requests.
- Calling Server for route/credential decisions.
- Injecting returned headers.
- Passing through unmatched local-mode traffic according to ADR-0003.

Proxy must not:

- Build provider auth state locally.
- Read credentials directly.
- Read identity private keys directly.
- Reconstruct server policy.

### CLI, RuntimeClient, UI

**Belongs to: client side**

These are interfaces into Server.

They may:

- Resolve client Identity.
- Sign requests.
- Call Server endpoints.
- Present output.

They must not:

- Own provider credential lifecycle.
- Write server registry directly except through Server endpoint.
- Reach into Vault internals.
- Decide provider authorization.

## Concrete Implementation Phases

### Phase 1: Storage Composition Foundation

Add a storage factory module.

Recommended behavior:

- Build raw local `DiskStore`.
- Build prefixed client/server/vault stores.
- Build AES-256-GCM encrypted vault store (`AesGcmEncryptionWrapper`).
- Return a small composition object, for example:

```python
class StorageGraph(BaseModel):
    client: AsyncKeyValue
    server: AsyncKeyValue
    vault: AsyncKeyValue
```

Use a dataclass if easier. Do not create an inheritance hierarchy.

Keep current local paths initially unless there is a direct reason to move them.

Expected result:

- Existing code can still use old wrappers while new repositories are introduced.
- No product behavior changes.
- Update `docs/UBIQUITOUS_LANGUAGE.md` with StorageSubstrate, StorageNamespace, and client/server split terms.

### Phase 2: Secret Source Chain

Introduce a shared secret source model.

Required sources:

- `EnvSecretSource`
  - Reads environment variables.
  - Never writes.
  - Highest priority.

- `KeyringSecretSource`
  - Reads/writes OS keyring.
  - Second priority.
  - Fails gracefully if keyring is unavailable.

- `LocalSecretSource`
  - Last-resort local fallback.
  - Uses client/server-local storage or local files with `0600` protection.
  - Acceptable because this matches current local fallback behavior.

Introduce `SecretResolver`.

Required behavior:

```python
resolver.get_or_create(name, factory)
```

Resolution:

1. Read env.
2. Read keyring.
3. Read local fallback.
4. Generate with factory.
5. Persist to first available writable source, preferring keyring then local fallback.
6. Never persist generated material to env.

Secret names:

```text
vault:master
identity:<handle>:private_key
ui:session_signing_key
```

Generate a 32-byte random key for AES-256-GCM. Store it under the secret name `vault:master`.

Expected result:

- Master key and identity private keys use one resolution model.
- Current config-backed encryption mode becomes implementation detail or transitional compatibility.
- Update `docs/UBIQUITOUS_LANGUAGE.md` with SecretSource and SecretResolver terms.

### Phase 3: IdentityRepository

Create one `IdentityRepository` implementation.

It composes:

```python
IdentityRepository(store: AsyncKeyValue, secrets: SecretResolver | None)
```

It should support both client and server identity records through methods, not subclasses.

Client-owned methods:

```python
create_local_identity(handle: str | None = None) -> IdentityMetadata
load_local_identity(handle: str) -> IdentityMetadata | None
get_active_identity() -> str | None
set_active_identity(handle: str) -> None
mark_registered(handle: str) -> IdentityMetadata
load_private_key(handle: str) -> Ed25519PrivateKey
```

Server-owned methods:

```python
register_public_identity(handle: str, did: str) -> IdentityRegistration
resolve_registration(handle: str) -> IdentityRegistration | None
list_registered_handles() -> list[str]
```

Enforce by wiring:

- Client repository receives a client namespace and secret resolver.
- Server repository receives a server namespace and no private-key resolver.
- Server code never calls private-key methods.

Do not create `ClientIdentityRepository` and `ServerIdentityRepository` unless later behavior truly diverges.

Expected result:

- Current `identity/keys.py`, `identity/client_config.py`, and `identity/registry.py` behavior is preserved behind one repository.
- Server private-key access is structurally absent.
- Update `docs/UBIQUITOUS_LANGUAGE.md` with IdentityRepository and IdentityRegistration terms.

### Phase 4: CredentialRepository

Create `CredentialRepository` over encrypted `AsyncKeyValue`.

Responsibilities:

- Save/load/delete `ConnectionRecord`.
- Save/load/delete `ProviderMetadataRecord`.
- Save/load/delete `ProviderStateRecord`.
- Save/load/delete server-scoped `ProviderClientRecord`.
- List provider groups for an identity.

It owns all credential key construction.

Preserve current semantics:

- Connection records are identity/handle-scoped.
- Provider metadata/state are identity/handle-scoped.
- Provider client records are server-scoped.
- `default` remains only a connection name, not identity/profile fallback.

Expected result:

- `AuthService` stops manually building storage keys.
- Store key parsing/building leaves general utility code or becomes repository-private.
- Update `docs/UBIQUITOUS_LANGUAGE.md` with CredentialRepository and vault namespace terms.

### Phase 5: ProviderRepository

Move custom provider persistence out of `AuthService`.

Responsibilities:

- Load bundled provider definitions.
- Load custom provider definitions from server namespace.
- Resolve custom overrides before bundled providers.
- Save/delete custom providers where policy allows.

Keep behavior unchanged.

Expected result:

- Auth can ask for providers through a collaborator.
- Provider persistence stops being mixed into credential lifecycle.
- Update `docs/UBIQUITOUS_LANGUAGE.md` with ProviderRepository term.

### Phase 6: Slim AuthService

Refactor `AuthService` to receive collaborators by composition:

```python
AuthService(
    identity: str,
    providers: ProviderRepository,
    credentials: CredentialRepository,
    deployment_mode: str,
)
```

Flow selection stays internal to `AuthService`. Flows are instantiated directly by string key (`"pkce"`, `"device_code"`, etc.) — no `FlowRegistry` type needed.

Keep AuthService focused on:

- Start login.
- Resume login.
- Refresh.
- Logout/revoke.
- API key validation.
- Return provider auth headers.

Move out of AuthService:

- Store key construction.
- Provider loading/persistence.
- Proxy route catalog construction.
- Server identity/policy checks.
- Export formatting if it remains CLI-specific.

Expected result:

- AuthService gets smaller and deeper.
- Tests can focus on auth behavior without constructing full storage state manually.
- Update module docstring to reflect new collaborator shape.

### Phase 7: Server Composition Root

Create explicit server state composition.

Recommended shape:

```python
class ServerState:
    storage: StorageGraph
    identities: IdentityRepository
    providers: ProviderRepository
    credentials: CredentialRepository
```

Auth is constructed on demand per-identity via a plain factory function — no `AuthServiceFactory` type:

```python
def make_auth_service(identity: str, state: ServerState) -> AuthService: ...
```

PoP JWT verification calls `verify_pop_jwt(...)` from `identity/proof.py` directly — no `ProofVerifier` wrapper.

Server dependencies should build from `ServerState`, not scattered constructors.

Replace placeholder `AuthService(identity="server")`.

Health/ready endpoints should use direct dependencies:

- storage health
- secret resolver health
- vault encrypted roundtrip
- registry availability

Expected result:

- Server is the only module that wires cross-domain workflows.
- The `identity="server"` placeholder disappears.
- Update architecture docs with the final `ServerState` shape.

### Phase 8: Proxy Server Authority

Move proxy route/credential decisions to Server-facing services.

Recommended behavior:

- Proxy asks Server for route catalog or per-request resolution.
- Server decides whether target matches a connected provider.
- Server returns:
  - pass-through
  - inject headers
  - future deny/proposal, not implemented now

Keep ADR-0003 behavior:

- unmatched local requests pass through.

Expected result:

- Proxy does not rebuild auth/provider logic locally.
- Proxy remains a transport/interface module.

### Phase 9: Documentation Final Review

Each preceding phase ships with its own doc update (see individual Expected Result sections). Phase 9 is a final consistency pass, not a catch-up.

Required at final review:

- Confirm `docs/UBIQUITOUS_LANGUAGE.md` reflects all terms introduced across phases: StorageSubstrate, StorageNamespace, SecretSource, SecretResolver, IdentityRepository, IdentityRegistration, CredentialRepository, ProviderRepository, client/server split.
- Confirm the AES-256-GCM encryption model is documented; remove any remaining Fernet references.
- Review `docs/adr/0002-server-registered-identities.md` — create a new ADR only if the implementation materially changes the accepted path-based ownership model.
- Confirm filesystem layout docs reflect `client/*` and `server/*` namespace separation.
- Confirm `default` is documented as a connection name only, never an identity or profile fallback.

## Required Tests

### Storage Tests

- Local storage graph uses one raw substrate with separate prefixed namespaces.
- Writing client namespace data does not appear in server namespace reads.
- Writing server namespace data does not appear in client namespace reads.
- Vault namespace stores AES-256-GCM encrypted payloads in the raw substrate.
- Repository callers never need raw collection names.

### Secret Source Tests

- Env source wins over keyring and local.
- Keyring wins over local when env is absent.
- Local fallback is used when env/keyring are unavailable.
- Generated secrets are not written to env.
- Generated secrets persist to keyring when available.
- Generated secrets persist to local fallback when keyring is unavailable.
- Missing secret plus failing writable sources returns a clear error.

### Identity Tests

- Creating a local identity stores metadata in client namespace.
- Creating a local identity stores private key through client-side secret resolver.
- Loading private key works from env.
- Loading private key works from keyring.
- Loading private key works from local fallback.
- Server registration stores only public registration fields.
- Server namespace never contains private key material.
- `registered` remains client-side cache only.
- `active_identity` remains client-side only.
- Protected request validation uses server registry, not client metadata.

### Credential Tests

- Connection record save/load roundtrips through encrypted vault store.
- Provider metadata/state remain identity-scoped.
- Provider client credentials remain server-scoped.
- Revoke behavior preserves current multi-identity semantics.
- Old `default` identity/profile behavior does not return.

### Auth Tests

- AuthService works with repositories instead of direct Vault key construction.
- Login session begin/resume still persists connection records.
- Refresh updates connection record and provider state.
- API key flow persists connection record.
- Auth does not import identity key-loading helpers.
- Auth does not import storage factory code.

### Server Tests

- Server validates PoP JWT and registry binding before constructing identity-scoped auth.
- Unknown handle is rejected.
- DID mismatch is rejected.
- App startup builds ServerState once.
- `/ready` no longer depends on `AuthService(identity="server")`.
- UI local identity resolution remains equivalent.
- Hosted/local policy behavior remains unchanged.

### Proxy Tests

- Proxy uses server-provided route/credential data.
- Matched provider request injects returned headers.
- Unmatched local-mode request passes through.
- Auth endpoint bypass remains intact.
- Ambiguous route behavior remains safe and tested.
- Proxy does not load credentials directly from repositories.

### Verification Commands

Run before claiming done:

```bash
uv run pytest
uv run ruff check src/ tests/
uv run ty check src/
uv run pre-commit run --all-files
```

## Non-Goals

- Do not implement a hosted product mode.
- Do not implement PostgreSQL deployment documentation.
- Do not implement migration from old file layout.
- Do not encrypt logical storage keys in this slice.
- Do not add network policy modes to proxy.
- Do not add approval/proposal flows.
- Do not create inheritance hierarchies for stores or repositories.
- Do not implement an `AuditRepository` or store audit events in KV. Audit is an append-only structured log (`audit.log`), not a queryable store.

## Open Concerns To Recheck Before Implementation

- Whether current tests rely on the raw encrypted value format of the old `VaultCrypto` — these will need updating when `AesGcmEncryptionWrapper` lands.
- Whether `py-key-value-aio` key enumeration is sufficient, or if repositories need explicit index records.
- Whether local fallback secrets should live in the same raw `DiskStore` or remain flat files for bootstrap simplicity.
- Whether moving `config.json` to the client namespace should happen in this slice or later.

## Recommended First Slice

Implement the smallest valuable slice first:

1. Add `SecretSource` chain.
2. Add storage graph factory using `AsyncKeyValue`, prefixes, and `AesGcmEncryptionWrapper`.
3. Move identity client metadata/registration behind `IdentityRepository`.
4. Keep existing `AuthService` mostly unchanged until identity/storage wiring is stable.
5. Add tests proving client/server namespace separation and private key non-leakage.

This first slice improves the architecture without expanding product behavior or forcing the whole AuthService refactor at once.
