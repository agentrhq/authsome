# Unified deployment flow: one registration + claim path for every deployment

The daemon previously branched on a deployment mode (`AUTHSOME_DEPLOYMENT_MODE`, defaulting to `local`) selected at startup, and ran two parallel implementations of nearly every ownership concept:

- **Local**: every Identity collapsed onto one synthetic Principal (`local@authsome.internal`); no claim was required; the Ed25519 PoP key was the only credential. Implemented by `LocalOwnershipResolver` and `LocalIdentityBootstrapService`.
- **Hosted**: each account was its own Principal authenticated by email+password in the browser; an Identity had to be explicitly claimed and accepted. Implemented by `HostedOwnershipResolver` and `HostedIdentityBootstrapService`.

Two code paths doubled the test surface, scattered `if get_deployment_mode() == "hosted"` branches across `dependencies.py`, `routes/_deps.py`, `routes/ui.py`, `routes/health.py`, and `credential_service.py`, and — most importantly — meant "local and hosted behave the same" was asserted in prose but never enforced in code, so the two paths were free to drift. The synthetic local Principal also had a latent wart: a second local Identity silently inherited the *admin* Principal and its Vault, which the hosted model would never allow.

## Decision

Collapse to a single flow, identical for every deployment. There is no deployment mode.

1. `authsome init` generates the Ed25519 Identity and registers it; the daemon returns `registration_status = "claim_required"` with a browser **claim URL**.
2. The user opens the claim URL and **registers (or logs in) with email + password**. The first Principal created on a server becomes **admin** (ADR 0006); all subsequent Principals are users.
3. The authenticated Principal **confirms the claim**, binding the Identity to the Principal and creating the Principal's default Vault.
4. PoP-authenticated calls are then authorized; `OwnershipResolver.resolve` requires an *accepted* claim.

The one irreducible difference between a single-machine and a networked deployment — *who authenticates the claiming Principal* — is resolved by always requiring the email+password browser step. Local is no longer special-cased; the local user is simply the first to sign up and therefore the admin.

The CLI (`AuthsomeApiClient.ensure_identity_ready`) was already mode-agnostic: it reacts to `claim_required` by opening the browser and polling, so it required no behavioural change. It now prints the claim URL to stderr so headless users can complete the step manually.

This supersedes the local/hosted split described in ADR 0003 (§ "local mode … hosted mode") and the "zero-config local" rationale in ADR 0006.

## Considered alternatives

**Single resolver with an injected claim-acceptance policy** (local auto-accepts, hosted requires a human). Keeps one code path while preserving local's zero-config experience. Rejected by explicit product decision: we want local and hosted to be byte-for-byte identical, with no second path or policy seam to maintain.

**Keep two resolvers, only harden with tests + docs.** Smallest change, but leaves the drift risk and duplicate test surface in place. Rejected.

## Consequences

- `AUTHSOME_DEPLOYMENT_MODE`, `get_deployment_mode()`, `LOCAL_PRINCIPAL_EMAIL`, the `Local*`/`Hosted*` resolver and bootstrap classes, and the `AuthService(deployment_mode=...)` parameter are all removed. `OwnershipResolver` and `IdentityBootstrapService` are single concrete classes.
- Admin enforcement is purely role-based: `_ensure_admin_operation_allowed` / `_ensure_provider_client_mutation_allowed` raise for any non-admin Principal, in every deployment (previously non-admins were implicitly allowed in local mode because the sole local Principal was always admin).
- The server-rendered UI always requires a hosted browser session; the local filesystem-identity UI path is gone. `HealthResponse.mode` is removed.
- **Breaking change.** Existing local installs have an Identity registered with no accepted claim and data under the `local@authsome.internal` Principal/Vault. After upgrading, those Identities are rejected until the user registers a Principal (email+password) and claims the Identity. A migration that rebinds the existing local Vault to a freshly registered Principal is possible but is intentionally out of scope here.
