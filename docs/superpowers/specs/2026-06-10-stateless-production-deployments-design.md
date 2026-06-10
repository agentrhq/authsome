# Stateless Production Deployments Design

## Summary

Prepare Authsome for stateless, horizontally scalable production deployments while preserving the local developer defaults. The server will select production infrastructure from environment variables: Postgres for the relational server Store when `AUTHSOME_DATABASE_URL` uses a Postgres scheme, and Redis for shared mutable server state plus encrypted vault KV when `AUTHSOME_REDIS_URL` is present.

The design keeps the existing module ownership model intact. `identity`, `auth`, and `vault` remain reusable libraries with infrastructure-agnostic contracts and domain behavior. `server` remains the composition root that chooses concrete infrastructure and combines the libraries into Authsome business logic.

## Goals

- Make container and multi-replica deployments viable without relying on local process memory or ephemeral disk for hot-path mutable state.
- Keep SQLite, disk vault storage, and in-memory transient state working for local development and tests.
- Reuse `py-key-value-aio` Redis support for vault storage instead of creating a custom Redis vault backend.
- Keep Postgres and Redis optional for library installs, while installing production extras in the Docker image.
- Provide self-hosting documentation with Postgres, Redis, Docker, and secret-management guidance.

## Non-Goals

- Do not introduce an ORM or Alembic for this refactor. Use a lightweight schema-version migration runner inside the existing Store adapter.
- Do not move business logic into CLI or proxy. They continue to communicate with the server.
- Do not add stateful browser sessions in this refactor. Browser sessions remain signed stateless JWT cookies.
- Do not add email verification or signup abuse prevention in this refactor. Those are tracked separately in GitHub issue #411.
- Do not introduce `AUTHSOME_VAULT_BACKEND`. Redis vault selection follows `AUTHSOME_REDIS_URL`.

## Current State

The current code already has a relational server Store split from vault storage:

- `src/authsome/server/store/database.py` supports SQLite and Postgres URL resolution, but Postgres uses a single `asyncpg` connection.
- `src/authsome/server/store/repositories.py` contains the five server-owned registries plus server config, custom provider definitions, and audit events.
- `src/authsome/server/dependencies.py` always creates the vault with `DiskStore`.
- `src/authsome/auth/sessions.py` stores auth flow sessions in process memory.
- `src/authsome/server/ui_sessions.py` keeps browser sessions stateless but stores pending identity-claim tokens in process memory.
- `src/authsome/identity/proof.py` validates PoP JWTs and currently owns an in-memory replay cache.
- `src/authsome/server/app.py` wires these components directly into `app.state`.

These defaults work for local development but do not work across multiple replicas. Auth flow sessions, pending claim tokens, and PoP replay JTIs need shared state. Vault encrypted blobs need a backend that survives container restarts without requiring a mounted local volume in production.

## Architecture

Authsome keeps the existing boundaries:

- `identity` owns identity and PoP token semantics. It creates PoP JWTs, verifies signatures, verifies request binding, and extracts proof claims. It remains infrastructure agnostic.
- `auth` owns flow/session models and abstract session-store behavior. Concrete Redis storage does not leak into auth flow code.
- `vault` owns encrypted KV semantics over an `AsyncKeyValue`. It does not define a Redis-specific vault API.
- `server` owns deployment topology. It selects SQLite or Postgres, DiskStore or RedisStore, memory or Redis state stores, and wires the selected implementations into services and routes.
- `cli` and `proxy` remain clients of the server business logic.
- `ui` and the relational Store remain server properties.

Backend selection is simple:

- `AUTHSOME_DATABASE_URL=postgresql://...` or `postgres://...` selects Postgres for the relational server Store.
- No Postgres URL selects SQLite.
- `AUTHSOME_REDIS_URL` selects Redis for auth flow sessions, pending claim tokens, PoP JTI replay cache, and raw vault KV.
- No Redis URL selects in-memory transient stores and disk vault KV.

If an explicit Postgres or Redis backend is configured and the driver is missing or the service is unreachable, startup fails. There is no runtime fallback from Redis/Postgres to memory/disk after startup.

Browser UI sessions stay stateless signed cookies for now. The disadvantages are known: server-side logout/revocation and active session visibility are not available. Verified signup and stateful browser-session management are deferred to issue #411.

## Components

### Server Configuration

`src/authsome/server/config.py` will add:

- `redis_url: str | None`
- Postgres pool settings, such as min and max pool size.
- TTL settings used by Redis-backed auth sessions, pending claim tokens, and replay cache where existing constants are currently hard-coded.

Configuration remains environment-driven through the existing `AUTHSOME_` prefix.

### Relational Store

`src/authsome/server/store/database.py` keeps the current lightweight adapter but upgrades production behavior:

- SQLite continues to use one `aiosqlite` connection.
- Postgres uses an `asyncpg` pool.
- Queries still use `?` placeholders at repository call sites, translated to Postgres positional parameters inside the adapter.
- Startup runs a lightweight schema-version migration runner.

The migration runner should:

- Maintain `store_schema_version`.
- Apply ordered migration functions or statements.
- Support SQLite and Postgres dialect fragments inside the Store module.
- Keep existing `CREATE TABLE IF NOT EXISTS` bootstrap behavior only as migration contents, not as ad hoc schema setup scattered through startup.

The existing registries remain repository classes. They should not learn about pools, Postgres clients, or migration internals.

### Replay Cache

The anti-replay cache prevents reuse of a PoP JWT within its validity window. Each PoP JWT has a `jti`. After signature, method, URL, body hash, and expiry validation, the server checks whether that `jti` has already been used. If it has, the request is rejected.

The split should be:

- `identity.proof` owns proof semantics and accepts an injected infrastructure-agnostic replay checker.
- A tiny protocol defines the operation shape: `check_and_store(jti: str, exp: int) -> None`.
- Server-side implementations provide storage:
  - Memory implementation for local dev and tests.
  - Redis implementation for production.

The Redis implementation should use an atomic set-if-not-exists operation with a TTL derived from `exp - now`. This lets replica B reject a JWT already accepted by replica A.

No Redis import belongs in `identity`.

### Auth Flow Sessions

`AuthSession` remains the domain model in `src/authsome/auth/sessions.py`.

The current in-memory `AuthSessionStore` behavior should be preserved behind a small store interface that covers the existing route needs:

- `create(...)`
- `get(session_id)`
- `save(session)`
- `delete(session_id)`
- `index_oauth_state(session)`
- `get_by_oauth_state(state)`

A Redis implementation can live server-side if it imports Redis-specific code. It should serialize `AuthSession` with Pydantic JSON, store each session under a namespaced key, and store OAuth state-to-session mappings under separate keys with matching TTLs.

Local memory behavior remains available when `AUTHSOME_REDIS_URL` is absent.

### Pending Claim Tokens

Browser sessions remain stateless in `UiSessionStore`, but pending claim tokens need shared mutable state so claim links survive replica changes.

The browser session methods stay simple:

- `create_browser_session(...)`
- `get_browser_session(cookie_value)`
- `build_cookie_value(token)`
- `delete_browser_session(cookie_value)`

Pending claim methods move behind a memory/Redis store:

- `create_pending_claim(identity, ttl_seconds)`
- `get_pending_claim(token)`
- `consume_pending_claim(token)`

`consume_pending_claim` should delete and return the token. The Redis version should be atomic where the Redis client makes that practical.

### Vault KV Backend

The vault continues to use `Vault -> AesGcmEncryptionWrapper -> AsyncKeyValue`.

`src/authsome/server/dependencies.py` chooses the raw `AsyncKeyValue`:

- No `AUTHSOME_REDIS_URL`: `DiskStore(directory=server_config.kv_store_dir)`
- `AUTHSOME_REDIS_URL`: `key_value.aio.stores.redis.RedisStore(url=server_config.redis_url)`

The existing `DekManager` continues to load or create the wrapped DEK record through the raw KV backend. Redis stores only encrypted vault values and DEK wrapping metadata. The vault master key is never stored in Redis.

### Secrets

Master-key resolution keeps the current behavior in `src/authsome/server/secrets.py`:

1. `AUTHSOME_MASTER_KEY`
2. `AUTHSOME_MASTER_KEY_FILE` or the default server key file
3. OS keyring
4. Generate a new base64 key, store it in keyring if possible, otherwise write the default key file

There is no special production-mode enforcement tied to Redis or Postgres. The self-hosting guide should recommend `AUTHSOME_MASTER_KEY` or `AUTHSOME_MASTER_KEY_FILE` for containers and explain that generated file keys only survive when the filesystem is persistent.

### App Lifecycle

`src/authsome/server/app.py` remains the composition root:

1. Load `ServerConfig`.
2. Open and migrate the relational Store.
3. If Redis is configured, create or validate Redis-backed state dependencies.
4. Create raw vault KV, load/create DEK, wrap with encryption, and construct `Vault`.
5. Create auth sessions, UI sessions/pending claim store, replay cache, provider repository, account auth service, bootstrap service, and ownership resolver.
6. Close Store pools and Redis-owned clients on shutdown.

The existing `ownership_cache = {}` can remain a local optimization only if it is not correctness-critical. If it can become stale across replicas for claim/binding changes, it should be removed or given a conservative TTL. Correctness must come from the registries, not the process cache.

## Data Flow

### Startup

Local startup without production URLs uses SQLite, DiskStore, and memory state. Postgres is selected only by a Postgres `AUTHSOME_DATABASE_URL`; Redis is selected only by `AUTHSOME_REDIS_URL`.

If Redis is configured, startup should ping Redis before serving requests. If Postgres is configured, startup should acquire a connection from the pool and run migrations before serving requests.

### PoP Requests

1. The request arrives with `Authorization: PoP <jwt>`.
2. `identity.proof.validate_proof_jwt()` validates the signature and request binding.
3. The injected replay checker stores the `jti` until expiry or raises if already seen.
4. The server resolves the identity registration and ownership through the relational Store.
5. The route receives the existing `ResolvedOwnership` and builds `CredentialService`.

### Auth Flow Sessions

1. A login flow creates an `AuthSession`.
2. The selected session store persists it with a TTL.
3. OAuth flows index `internal_state` to the session id.
4. Callback routes resolve the session by OAuth state or session id, update the session, and save it.
5. Expired or missing sessions behave as not found.

### Pending Claim Links

1. Identity bootstrap creates a pending claim token.
2. The selected pending claim store persists it with a TTL.
3. The claim route consumes the token.
4. Consumed or expired tokens behave as not found.

### Vault Access

1. `CredentialRepository` reads or writes credentials through `Vault`.
2. `Vault` updates its index records and plaintext domain values.
3. `AesGcmEncryptionWrapper` encrypts the values.
4. DiskStore or RedisStore stores encrypted blobs using the existing collection/key naming scheme, including `vault:<vault_id>:...` collections.

## Error Handling

Startup failures:

- Invalid database URL scheme fails clearly.
- Postgres driver missing, connection failure, bad credentials, or migration failure fails startup.
- Redis driver missing, connection failure, bad credentials, or ping failure fails startup.
- Vault DEK unwrap failure fails startup.

Runtime behavior:

- Redis outages during affected operations return 5xx responses. The server does not silently fall back to memory or disk.
- PoP replay detection returns the existing unauthorized proof-validation response.
- Expired sessions and pending claim tokens behave as not found.
- Health remains cheap and public. Keep `/api/health` and add a root `/health` alias for container health checks.
- Readiness checks the relational Store and vault. If Redis is configured, readiness also checks Redis connectivity.

## Docker And Self-Hosting

The Docker image should install production extras by default while the base Python package keeps them optional where possible.

The Dockerfile should:

- Keep a multi-stage build for UI and Python package.
- Use the `uv` toolchain for Python build/install.
- Run as a non-root user.
- Expose port 7998.
- Add a root `/health` alias backed by the same response as `/api/health`.
- Include a healthcheck against `/health`.

`docker-compose.yml` should include:

- `authsome`
- `postgres`
- `redis`

The self-hosting guide should cover:

- Prerequisites: Docker, Postgres, Redis.
- Environment variables: `AUTHSOME_DATABASE_URL`, `AUTHSOME_REDIS_URL`, `AUTHSOME_MASTER_KEY`, `AUTHSOME_MASTER_KEY_FILE`, `AUTHSOME_HOME`, `AUTHSOME_BASE_URL`, `AUTHSOME_HOST`, `AUTHSOME_PORT`, and analytics settings.
- Startup steps: pull or build image, set env vars, start service, run `authsome init`, verify `/health`.
- Compose example for local production simulation.
- Secret guidance: do not commit production `AUTHSOME_MASTER_KEY`; prefer a cloud secret manager, Doppler, Vault, or platform secrets.
- Migration guidance: relational schema migrations run at startup; back up Postgres and Redis according to operator policy.

## Testing

Default `uv run pytest` should continue to pass without external services.

Tests to add or adjust:

- SQLite migration tests.
- Postgres migration tests gated behind an optional service fixture or environment variable.
- Postgres pool adapter tests gated behind the same integration mechanism.
- Memory replay cache tests after moving it out of `identity`.
- Redis replay cache tests for duplicate rejection and TTL behavior.
- Auth session store contract tests run against memory and Redis implementations.
- Pending claim store contract tests run against memory and Redis implementations.
- Vault backend tests showing RedisStore is selected when `AUTHSOME_REDIS_URL` is present and values remain encrypted.
- Server lifecycle tests for local defaults and Redis/Postgres selection failures.
- Existing session recreation tests should split local and Redis behavior: memory sessions do not survive app recreation; Redis sessions do.
- Docker smoke test for image build and `/health`.

Verification before completion should include:

- `uv run pytest`
- `uv run ruff check`
- `uv run ty check`
- Docker build smoke test when Docker is available
- Redis/Postgres integration tests when services are available

## Rollout Plan

Implement in small phases inside one production-readiness branch:

1. Add config fields and optional dependency extras.
2. Upgrade the relational Store to Postgres pooling and lightweight migrations.
3. Split replay-cache semantics cleanly from `identity` and add memory/Redis implementations.
4. Introduce auth session store contracts and Redis-backed auth sessions.
5. Split pending claim storage from stateless browser session signing and add Redis pending claims.
6. Reuse `py-key-value-aio[redis]` for vault raw KV when `AUTHSOME_REDIS_URL` is configured.
7. Update app lifecycle, readiness, Dockerfile, compose, and self-hosting docs.
8. Add gated integration tests and smoke verification.

Each phase should preserve local defaults and keep implementation changes close to the modules that own the behavior.

## Open Follow-Up

GitHub issue #411 tracks hosted login hardening outside this refactor:

- Email verification during signup.
- Signup abuse prevention.
- Stateful browser sessions.
- Server-side browser-session logout and revocation.
- Session visibility and account-security policies.
