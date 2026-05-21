# AGENTS.md

This file provides guidance to AI coding agents (Claude Code, Codex, Copilot, etc.) when working with this repository.

## Commands

Always use `uv run` to execute commands — do not use `python`, `python3`, `pip`, or bare tool names directly.

```bash
# Install in editable mode (required before running anything)
uv pip install -e ".[dev]"

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_client.py

# Run a single test by name
uv run pytest tests/test_client.py::test_login_pkce -v

# Run tests with coverage
uv run pytest --cov=authsome
```

Run linting and type checks:
```bash
# Lint and auto-fix
uv run ruff check --fix src/ tests/

# Format
uv run ruff format src/ tests/

# Type check
uv run ty check src/
```

The CLI entry point after install:
```bash
uv run authsome init
uv run authsome login github
uv run authsome list
```

## Engineering principles

> For the full set of contribution guidelines, design principles, and AI-assisted development practices, see [CONTRIBUTING.md](CONTRIBUTING.md). Everything in that document applies to AI agents as well as human contributors.



These rules govern all changes to this codebase — apply them without exception.

**YAGNI.** Implement only what the current task demands. Don't build for hypothetical future requirements.

**Use trusted libraries over reinventing.** Reach for a well-maintained dependency before writing your own crypto, HTTP client, or token parser.

**Deep modules over shallow ones.** Prefer a small surface area with rich internals over many thin wrappers. More files is not more modular.

**Composition over inheritance.** Prefer small collaborators wired together through explicit dependencies over inheritance hierarchies. Use inheritance only when there is a real subtype relationship and composition would make the design less clear.

**Single responsibility and separation of concerns.** Auth authenticates. Vault stores credentials. CLI presents output. A flow must not write to storage; storage must not know about OAuth. If a function is hard to name, it's doing too many things.

**No premature optimization.** Don't add caching, batching, or concurrency before a measured performance problem exists. Simple and slow is fixable; complex and wrong is not.

**Don't do it just because you can.** Clever is a cost. If a feature, abstraction, or refactor doesn't solve a real problem that exists today, skip it.

**Leave it better than you found it.** Fix a nearby typo, remove a dead import, or clarify a confusing comment while you're in the area — not the whole file, just the immediate vicinity.

**Comment the why, not the what.** Use Google-style docstrings for public interfaces. Inline comments explain non-obvious invariants, workarounds, or hidden constraints — not what the code already says.

**Update docs with code.** If you change behavior, update the relevant docstring, `README.md`, or `CONTRIBUTING.md` in the same commit.

## AI agent rules

**Verify before claiming done.** Run `uv run pytest`, `uv run ruff check`, and `uv run ty check`. Confirm they pass before stating work is complete. Never assume.

**Minimal blast radius.** Change only what was asked. Don't refactor, rename, or reorganize while implementing a feature — save cleanup for a dedicated commit.

**Surface uncertainty.** If multiple valid approaches exist, present the tradeoffs. Don't silently pick one and hide the decision.

**No hallucinated APIs.** If unsure a method or parameter exists, search the codebase before using it.

**Read before write.** Understand the existing implementation before modifying it.

**Prefer reversible changes.** Avoid destructive operations without explicit user confirmation.

**Small, focused commits.** One logical change per commit. Resist the urge to batch unrelated changes.

**Explain the why in commit messages.** The diff shows what changed; the message says why.

**Never commit directly to `main`.** All changes must go through a pull request. Create a feature or chore branch, push it, and open a PR — even for single-line fixes.

---

## Conventions

**Commits and PRs:** Use [Conventional Commits](https://www.conventionalcommits.org/) style — `feat:`, `fix:`, `chore:`, `docs:`, `refactor:`. Mark breaking changes with `!` (e.g., `feat!:`) or a `BREAKING CHANGE:` footer.

**Branches:** Use Gitflow-style branch names with a short kebab-case description. Prefer `feature/<description>` for new capabilities, `bugfix/<description>` for non-urgent fixes, `hotfix/<description>` for urgent production fixes, `release/<version>` for release preparation, and `support/<description>` for maintenance lines.

**Pre-commit:** This repo uses `pre-commit` with ruff for lint and format. Run `pre-commit run --all-files` before finishing any change. The hook runs automatically on `git commit`.

**Available skills:** `ruff`, `uv`, `ty`, `uv-trusted-publish-github-action`, `release-please-changelog` are installed in `.claude/skills/`.

## Architecture

**Identity (`src/authsome/identity/local.py`)** manages local Ed25519 key pairs and `did:key` DIDs. Key material lives at `~/.authsome/identities/<handle>.key` (mode `0600`); metadata at `~/.authsome/identities/<handle>.json`. An Identity is a cryptographic agent — it is not a credential namespace. Credential namespacing is owned by a Vault (see below).

**Principal & Vault domain models (`src/authsome/identity/principal.py`)** define the two concepts that own credentials. A **Principal** is a non-cryptographic logical partition (human or team) identified by an opaque `PrincipalId`. A **Vault** is a named credential store owned by exactly one Principal and identified by an opaque `VaultId`. Credentials are scoped to a vault: `vault:<vault_id>:...`. An Identity claims membership in a Principal via an `IdentityClaimRecord`; the claim must be accepted before vault access is granted.

**Five server-owned registries** persist in `~/.authsome/server/` and are implemented in `src/authsome/server/registries.py`:
| Registry | File | Authoritative for |
|----------|------|-------------------|
| `IdentityRegistry` | `identity_registry.json` | Handle → DID mapping (PoP JWT validation) |
| `PrincipalRegistry` | `principal_registry.json` | PrincipalId → email |
| `VaultRegistry` | `vault_registry.json` | VaultId → VaultHandle |
| `IdentityClaimRegistry` | `identity_claim_registry.json` | Identity → Principal claim + ClaimStatus |
| `PrincipalVaultBindingRegistry` | `principal_vault_binding_registry.json` | Principal → default Vault binding |

**PoP Auth (`src/authsome/identity/proof.py`)** implements Proof-of-Possession JWT creation and validation. Every protected daemon request carries `Authorization: PoP <jwt>` signed with the local Ed25519 key. The JWT is bound to the specific HTTP method, path, and body SHA-256. The daemon validates the signature, checks the `jti` replay cache, and confirms `sub` (handle) → `iss` (DID) via the Identity Registry.

**AuthService (`src/authsome/server/credential_service.py`)** is the authentication and credential lifecycle coordinator. It owns OAuth flows, token refresh, login/logout/revoke. Lives in `server/` because it coordinates `auth/` flows with `vault/` storage and `audit/` logging. Constructed with `(vault, identity, principal_id, vault_id)`; all credential store keys are namespaced as `vault:<vault_id>:...`. The caller (server dependency injection) resolves `vault_id` from the `PrincipalVaultBindingRegistry` before constructing `AuthService`.

**Flows (`src/authsome/auth/flows/`)** implement the `AuthFlow.authenticate()` interface. Each flow returns a `ConnectionRecord`. The `auth/` module is a leaf — it imports nothing from `vault/`, `audit/`, or `server/`.

| Flow | Class | Notes |
|------|-------|-------|
| `pkce` | `PkceFlow` | Spins up an HTTP server on port **7999** for the OAuth callback |
| `device_code` | `DeviceCodeFlow` | Polls token endpoint; no browser needed |
| `dcr_pkce` | `DcrPkceFlow` | Dynamic Client Registration then PKCE |
| `api_key` | `ApiKeyFlow` | Prompts via secure browser bridge |

**Provider Registry** resolves providers in this order: custom providers stored in the vault under the `providers` collection override bundled JSON in `src/authsome/auth/bundled_providers/`. Bundled providers (GitHub, Google, Okta, Linear, OpenAI) are loaded via `importlib.resources`.

**Vault (`src/authsome/vault/`)** is the encrypted KV store. The master key lives at `~/.authsome/server/master.key` (mode `0600`) or in the OS keyring. All credential blobs are encrypted at rest; the AuthService reads and writes plaintext through the Vault without knowing encryption details.

**Storage** uses a DiskStore-backed KV at `~/.authsome/server/kv_store/`. Store keys follow the pattern:
```
vault:<vault_id>:<provider>:connection:<connection_name>
vault:<vault_id>:<provider>:metadata
vault:<vault_id>:<provider>:state
server:<provider>:client
```

**Config** (`GlobalConfig`) is stored in the KV store under `config/global`. Key fields: `active_identity` (the handle of the current identity), `vault_id` (the active vault resolved at `authsome init`). Encryption mode is set via `config.encryption.mode` (`local_key` or `keyring`).

**CLI (`src/authsome/cli/main.py`)** is Click-based. All commands support `--json` for machine-readable output. `authsome init` creates the local identity, registers it with the daemon, and writes `active_identity` to config.

## Agent skills

### Issue tracker

Issues live in GitHub Issues for `agentrhq/authsome`. See `docs/agents/issue-tracker.md`.

### Triage labels

Default canonical labels (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
