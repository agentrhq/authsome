# authsome

authsome is the local auth layer for AI agents — it answers which agent, acting on behalf of whom, accessed what credential, and was that allowed.

## Language

### Ownership & Identity

**Principal**:
A logical partition representing a human or team that owns one or more Vaults and performs OAuth authorization flows to acquire credentials. Identified by a human-readable **PrincipalHandle** (e.g., `manoj`); the sentinel `default` is used in local mode. Has no cryptographic key of its own.
_Avoid_: User, account, owner, human, Profile

**PrincipalHandle**:
The human-readable name for a Principal (e.g., `manoj`). Stable storage key — uniqueness is global. In local mode the PrincipalHandle is always `default`. In hosted mode it is assigned at Principal creation and backed by a PrincipalRegistry entry.
_Avoid_: principal_id, principal_name, username

**Vault**:
A credential store owned by exactly one Principal. Identified by a **VaultHandle**. Stores OAuth tokens and secrets encrypted at rest. A Principal may own multiple Vaults (e.g., `default`, `prod`, `dev`); every Principal has a designated **default Vault** used when no vault is specified. In local mode the default Vault is created automatically during `authsome init`.
_Avoid_: credential store, token store, secret store

**VaultHandle**:
The human-readable name for a Vault (e.g., `default`, `prod`, `dev`). Stable storage key scoped to a Principal — uniqueness is `(PrincipalHandle, VaultHandle)`. In local mode the VaultHandle is always `default`.
_Avoid_: vault_id, vault_name

**Claim**:
The act of an Identity asserting membership in a Principal, recorded as an `IdentityRegistration` with a `ClaimStatus`. In local mode all claims are auto-accepted. In hosted mode a Principal must explicitly accept a Claim before the agent may access the Principal's vault.
_Avoid_: Registration request, join request, enrollment

**ClaimStatus**:
The lifecycle state of a Claim: `pending` (submitted, awaiting human review), `accepted` (agent may access vault), `rejected` (agent denied access).
_Avoid_: Registration status, identity state

**PrincipalRegistry**:
The daemon-owned authoritative registry of Principals (PrincipalHandle → email). In local mode the `default` Principal is implicit and requires no registry entry. In hosted mode every Principal must have a registry entry before agents can register under it.
_Avoid_: User table, account store

**VaultRegistry**:
The daemon-owned authoritative registry of Vaults (VaultHandle + owning PrincipalHandle). In local mode the `default` Vault is created implicitly during `authsome init`. Separate from PrincipalRegistry — three registries together form the complete domain model: Principals, Identities, Vaults.
_Avoid_: vault table, vault store

**Identity** (Agent):
The cryptographic agent — an Ed25519 key pair, a `did:key` DID, and a Handle. Owned by a Principal. Authenticates to the daemon via PoP JWTs.
_Avoid_: User, account, actor

**Handle**:
The human-readable name for an Identity (e.g., `brisk-boldly-clearly-1234`). Registered with the Identity Registry; used as the `sub` claim in PoP JWTs.
_Avoid_: Username, alias, profile name

## Initialization & Claim Flow

**Local mode**: `authsome init` creates an Identity, registers it under the implicit `default` Principal with `claim_status = accepted`, and creates the `default` Vault for that Principal. No `--principal` or `--email` flags required or accepted.

**Hosted mode**: `authsome init --principal manoj --email manoj@agentrq.dev` creates the Principal in the PrincipalRegistry if absent, creates a new Identity, and registers a **Claim** — an `IdentityRegistration` with `claim_status = pending`. The agent cannot access the Principal's vault until the Principal accepts the claim. A human reviews pending claims in the UI and accepts or rejects each one.

`ensure_initialized` implicit key generation is removed — init is always explicit.

`IdentityRegistration` always carries a `principal` field (default `"default"` in local) and a `claim_status` field.

**Claim lifecycle**: `pending` → `accepted` | `rejected`

A `pending` agent can authenticate to the daemon (PoP JWT validation succeeds) and inspect its own claim status. All vault reads and writes are gated — the daemon returns `403` for any credential operation until the Claim is `accepted`.

## Relationships

- A **Principal** owns one or more **Identities** (agents).
- A **Principal** owns one or more **Vaults**; every Principal has a designated default Vault.
- An **Identity** belongs to exactly one Principal.
- **Identities** access credentials from their owning Principal's default Vault (or an explicitly specified Vault).
- `IdentityRegistration` carries a `principal_handle` field — the authoritative forward link (Identity → Principal).
- `VaultRegistration` carries a `principal_handle` field — the authoritative forward link (Vault → Principal).

## AuthService

`AuthService` is constructed with four arguments: `vault`, `principal` (PrincipalHandle), `vault_handle` (VaultHandle — together they drive the vault namespace), and `identity` (agent Handle — used only for audit logging). `_coll = f"vault:{self._principal}:{self._vault_handle}"`. The `identity` field does not influence which vault namespace is accessed. The caller (daemon dependency injection) resolves the correct VaultHandle before constructing AuthService; AuthService is a pure credential-access layer.

## On-Behalf-Of Model

Every agent action is implicitly "on behalf of" its Principal. `authsome list` returns all connections owned by the Principal — any accepted agent under that Principal sees the full set. Per-agent visibility filtering is deferred to the policy layer. The audit log records both `identity` and `principal` on every event, so the acting agent is always traceable.

## Login & Credential Ownership

`authsome login <provider>` is always agent-triggered. The daemon resolves the agent's Principal from `IdentityRegistration.principal`, executes the OAuth flow (human approves in browser), and writes the token to the Principal's vault namespace. All accepted agents under that Principal immediately share the credential. A UI-initiated login path may be added later but is not required now.

## Audit

Every `AuditEvent` carries two required top-level fields: `identity` (the agent Handle) and `principal` (the PrincipalHandle). Neither is optional — every auditable action has both an acting agent and an owning principal.

## Migration

Breaking change shipped in v0.4. No migration path — existing vault data under `identity:<handle>:...` keys is abandoned. Users re-run `authsome login` after upgrading. See CHANGELOG for the breaking change notice.

## Flagged ambiguities

- **"User"** previously appeared as an alias-to-avoid for Identity. With this design, a User/human maps to **Principal** — a distinct, non-cryptographic concept. Do not use "user" in code or docs; use **Principal**.
- **"Profile"** was the credential namespace scoped to an Identity Handle. It is now retired. Profile = Principal — same concept, less precise name. Use **Principal** everywhere. `ProfileMetadata` was already removed; `profile:` store key prefix is replaced by `principal:`.
- **"identity"** in `AuthService(identity=...)` referred to the handle used as a vault namespace key. That parameter now means the agent handle used for audit logging only; vault namespace is resolved from `principal`.
