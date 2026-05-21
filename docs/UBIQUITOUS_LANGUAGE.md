# Ubiquitous Language

## Architecture Layers

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Vault** | The secure credential store. Owns the master key and DiskStore-backed KV storage. Exposes a generic encrypted key-value interface (`get`/`put`/`delete`/`list`). Encrypts full record blobs at rest. Does not know about credential types or token lifecycle. | Store, keystore, secret store |
| **AuthLayer** | The authentication and credential lifecycle layer (`AuthService`, exported as `AuthLayer`). Owns OAuth flows, token refresh, login/logout/revoke. Receives Vault as a dependency. | Auth client, auth service |
| **CliRuntime** | The runtime wiring container assembled once per CLI invocation (`src/authsome/cli/context.py`). Holds a `RuntimeClient` (HTTP client for daemon requests) and a `ProxyRunner`. No business logic of its own. | Client, session, app, AuthsomeContext |
| **RuntimeClient** | The CLI's internal async HTTP client for daemon requests. Attaches PoP JWT headers to protected requests and manages identity bootstrapping. | Daemon client, HTTP client |
| **Sensitive** | A field annotation (`Annotated[str, Sensitive()]`) marking fields that contain secret values and must be redacted before display or logging. The `redact()` utility in `utils.py` inspects this annotation to replace values with `"***REDACTED***"`. | Secret field, encrypted field |

## Principals & Ownership

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Principal** | A logical partition representing a human or team that owns a Vault namespace and performs OAuth authorization flows to acquire credentials. Identified by a **PrincipalHandle**; the sentinel `default` is used in local mode. Has no cryptographic key. | User, account, owner, Profile |
| **PrincipalHandle** | The human-readable username for a Principal (e.g., `manoj`), used as the vault namespace key (`principal:<handle>:...`). Always `default` in local mode. | principal_id, username |
| **PrincipalRegistry** | Daemon-owned mapping from PrincipalHandle → email plus a cached `identity_handles` list for UI queries. Only exists in hosted mode; local mode has no registry entry — `default` is implicit. | User table, account store |
| **Claim** | An Identity's assertion of membership in a Principal, recorded as an `IdentityRegistration` with a `ClaimStatus`. Local mode auto-accepts all claims. Hosted mode requires explicit Principal approval. | Registration request, join request |
| **ClaimStatus** | Lifecycle state of a Claim: `pending` (awaiting review), `accepted` (vault access granted), `rejected` (vault access denied). | Registration status |

## Identity & Authentication

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Identity** | The cryptographic agent — an Ed25519 key pair, a `did:key` DID derived from the public key, and a human-readable Handle. Owned by a Principal. Created by `authsome init`; the Handle/DID pair is registered with the daemon before any protected request. | User, account, actor |
| **Handle** | The human-readable name for an Identity (e.g., `brisk-boldly-clearly-1234`). Assigned at `init` time, registered with the Identity Registry, and used as the `sub` claim in every PoP JWT. | Username, alias, profile name |
| **DID** | A `did:key` Ed25519 identifier derived deterministically from the Identity's public key. Encoded as `did:key:z<base58(0xed01 + raw_pubkey)>`. Appears as `iss` in PoP JWTs; the daemon verifies the signature against the public key embedded in the DID. SPIFFE URI support may be added in a future release. | Key ID, public key identifier |
| **PoP JWT** | A short-lived (60 s) Proof-of-Possession JWT signed with the Identity's Ed25519 private key. Bound to a specific HTTP request via `htm` (method), `htu` (path+query), and `body_sha256`. Claims: `iss` = DID, `sub` = Handle, `jti` for replay prevention. Sent as `Authorization: PoP <token>`. | Auth token, bearer token, signed request |
| **Identity Registry** | The daemon-owned authoritative mapping from Handle → DID + `principal_handle` + `claim_status`, persisted at `~/.authsome/server/identity_registry.json`. A protected request is accepted only when the PoP JWT's `sub` is a registered Handle with an `accepted` Claim and the registry maps that Handle to the same DID as `iss`. | Identity store, key registry |
| **Provider** | An external service (GitHub, Google, OpenAI, etc.) identified by a unique name and described by a `ProviderDefinition` | Service, integration, app |
| **AuthType** | The authentication mechanism a provider uses — either `oauth2` or `api_key` | Auth method, auth strategy |
| **Flow** | The specific protocol executed to obtain credentials for a provider (PKCE, Device Code, DCR+PKCE, API Key) | Auth flow, login flow, grant type |
| **Connection** | A named, authenticated session binding a Principal to a Provider; holds credentials. All accepted agents under a Principal share its Connections. | Credential, token, session, auth |
| **ConnectionStatus** | The lifecycle state of a Connection: `connected`, `expired`, `revoked`, `invalid`, `not_connected` | Status, state |
| ~~**Profile**~~ | *Retired in v0.4.* Profile was the credential namespace scoped to an Identity Handle. That role is now owned by **Principal**. Vault keys moved from `profile:<handle>:...` / `identity:<handle>:...` to `principal:<handle>:...`. | — |
| **Scope** | An OAuth2 permission requested from a Provider during a Flow | Permission, role |

## Provider Configuration

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **ProviderDefinition** | The complete JSON schema describing a provider's AuthType, Flow, OAuth endpoints, and export mapping | Provider config, provider spec |
| **BundledProvider** | A ProviderDefinition shipped inside the library package | Built-in provider, default provider |
| **ProviderRegistry** | The system that resolves a provider name to its ProviderDefinition, checking local overrides before bundled definitions | Provider loader, provider resolver |
| **OAuthConfig** | The OAuth2-specific section of a ProviderDefinition (authorization URL, token URL, PKCE support, etc.) | OAuth settings |
| **ApiKeyConfig** | The API-key-specific section of a ProviderDefinition (header name and prefix) | API key settings |
| **ClientCredentials** | The OAuth2 `client_id` and `client_secret` configured for a Provider within a Profile, stored in a `ProviderClientRecord` | OAuth client, app credentials |

## Storage & Credentials

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **IdentityMetadata** | Client-side record for a local Identity, stored at `~/.authsome/identities/<handle>.json`. Fields: `handle`, `did`, `registered` (bool), `created_at`, `updated_at`. Written by the CLI; never read by the daemon. | Identity record, key metadata |
| **IdentityRegistration** | Daemon-owned record in the Identity Registry binding a Handle to a DID. Fields: `handle`, `did`, `created_at`, `updated_at`. Authoritative for PoP JWT validation. | Registry entry, daemon identity |
| **ConnectionRecord** | The persisted credential record for a Connection: plaintext tokens or API key (encrypted at rest by the Vault), scopes, expiry, and account info. `schema_version = 2`. | Token record, credential record |
| **ProviderMetadataRecord** | Non-secret per-profile record tracking which Connections exist for a Provider and which is the default | Provider metadata |
| **ProviderStateRecord** | Transient per-profile record tracking the last refresh attempt and any errors for a Provider | Provider state |
| **AccountInfo** | The identity fields (id, label) returned by a Provider and stored on a ConnectionRecord | User info, identity |
| **ClientCredentials** | The OAuth2 `client_id` and `client_secret` for a Provider, stored in a `ProviderClientRecord` at server scope (key: `server:<provider>:client`). Shared across all Profiles and users on a server instance — they represent the OAuth application registration, not the user. | User credentials, per-profile client |
| ~~**EncryptedField**~~ | *Removed.* No longer part of the public model layer. Encryption is now handled entirely within the Vault. Tokens are stored as plaintext `str` on `ConnectionRecord` and marked with the `Sensitive` annotation for display safety. | — |
| ~~**CredentialStore**~~ | *Deprecated.* Internal implementation detail of the Vault. Do not use in documentation or code outside `vault/`. | — |
| ~~**CryptoBackend**~~ | *Deprecated.* Internal implementation detail of the Vault. Do not use in documentation or code outside `vault/`. | — |
| ~~**ProfileMetadata**~~ | *Removed.* Profile is now a credential namespace scoped by the Identity Handle; no separate metadata record is stored. | — |

## Flows

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **PKCE Flow** | Browser-based OAuth2 authorization code grant with PKCE; spins up a local callback server | OAuth flow, browser flow |
| **Device Code Flow** | Headless OAuth2 via device authorization endpoint; polls until the user authorizes on another device | Headless flow, device flow |
| **DCR PKCE Flow** | Dynamic Client Registration followed immediately by a PKCE Flow; used when providers require per-client registration | Dynamic registration flow |
| **API Key Flow** | Collects an API key from the user via a Browser Bridge and stores it as a ConnectionRecord | Key flow |
| **Browser Bridge** | A short-lived local HTTP server that presents a secure form to collect secrets (API keys) from the user interactively | Secure input, form server |

## Proxy

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **AuthProxy** | A local mitmproxy-based HTTP proxy that intercepts outgoing requests and injects auth headers from active Connections | Proxy, HTTP proxy |
| **RunningProxy** | A handle to an AuthProxy running in a background thread, with a `shutdown()` method | Proxy handle, proxy instance |

## Relationships

- A **Principal** owns one or more **Identities** and is bound to one or more **Vaults** via a **PrincipalVaultBinding**. The credential namespace is keyed by the opaque **VaultId** (`vault:<vault_id>:...`), not by PrincipalHandle.
- An **Identity** is owned by exactly one **Principal**; the ownership is recorded in **IdentityRegistration** as `principal_handle`.
- Every Identity action is implicitly "on behalf of" its Principal — all accepted agents under a Principal share its **Connections**.
- A **Principal** contains zero or more **Connections**, each scoped to one **Provider**.
- A **Connection** is created by exactly one **Flow**; the FlowType is determined by the **ProviderDefinition**.
- A **ConnectionRecord** belongs to exactly one **Connection** and one **Principal**. Tokens are plaintext on the record; the **Vault** handles encryption transparently at write time.
- A **ProviderRegistry** resolves a provider name by checking local `~/.authsome/providers/` overrides before **BundledProviders**.
- The **Vault** encrypts full **ConnectionRecord** blobs using the master key it manages (file-based or OS keyring). The **AuthLayer** reads and writes records through the Vault without knowing the encryption details.
- An **AuthProxy** draws credentials from **Connections** owned by the active Principal via the **AuthLayer** and injects them as request headers.
- **CliRuntime** wires **RuntimeClient** and **ProxyRunner** together; the CLI creates one runtime per invocation via `ContextObj.initialize()`.
- **ClientCredentials** are server-scoped. A single `ProviderClientRecord` per Provider is shared by all Principals on a server instance. `ConnectionRecord` tokens are always principal-scoped.
- A **PoP JWT** is issued by the CLI for each protected daemon request. The daemon validates the signature against the **DID** embedded in `iss`, checks the **Identity Registry** to confirm `sub` (the Handle) maps to that DID with `claim_status = accepted`, resolves the **Principal** via `IdentityClaimRecord.principal_id`, then looks up the default **VaultId** via **PrincipalVaultBindingRegistry** to construct **AuthService** with the correct credential namespace.

## Example dialogue

> **Dev:** "If I call `authsome login github`, does it create a new **Principal**?"
>
> **Domain expert:** "No — `login` adds a **Connection** to the calling agent's **Principal**. The agent's `IdentityRegistration` carries a `principal_handle`; the daemon resolves that and writes the token to `principal:<handle>:github:connection:default`. Any other accepted agent under that Principal can use it immediately."
>
> **Dev:** "So the **Connection** is what I query later to get the access token?"
>
> **Domain expert:** "Exactly. `get_access_token` looks up the **ConnectionRecord** for that **Provider** + **Principal** combination through the **Vault** (which decrypts transparently) and returns the plaintext token."
>
> **Dev:** "And if the token is expired, does it auto-refresh?"
>
> **Domain expert:** "Yes — the **ConnectionStatus** will show `expired`, and the **ConnectionRecord** holds the `refresh_token` so the **AuthLayer** can exchange it without re-running the **Flow**. The outcome is a new **ConnectionRecord** with updated tokens and `status = connected`."
>
> **Dev:** "What if I need two GitHub accounts under the same Principal?"
>
> **Domain expert:** "Create two named **Connections** — `authsome login github --connection work` and `authsome login github --connection personal`. Both live under `principal:<handle>:github:connection:work` and `principal:<handle>:github:connection:personal`. All agents under that Principal can access either."
> **Dev:** "What if I need to connect to two GitHub accounts?"
>
> **Domain expert:** "Use two **Profiles** — one per identity context. Each **Profile** has its own scoped keys in the **Vault**, so the two **Connections** to the `github` **Provider** are completely isolated."

## Flagged ambiguities

- **"client"** can mean the `RuntimeClient` (the CLI's internal HTTP client for daemon requests) or `ClientCredentials` (the OAuth2 `client_id`/`client_secret` pair). Use **RuntimeClient** for the former and **ClientCredentials** / `ProviderClientRecord` for the latter.
- **"flow"** is used as both a `FlowType` enum value (a string like `"pkce"`) and an `AuthFlow` instance (the object that executes the protocol). Distinguish by saying **flow type** for the enum and **flow** or **flow handler** for the runtime object.
- **"provider"** can mean a provider name string (`"github"`), a `ProviderDefinition` object, or a row in the ProviderRegistry. Prefer **Provider** (capitalized) for the concept, **ProviderDefinition** for the JSON schema, and **provider name** for the identifier string.
- **"credential"** was used loosely in early documentation to mean both a **Connection** (the full authenticated session) and a specific secret (the token). Use **Connection** for the session and **access token** / **API key** for the individual secret values.
- **"identity"** can mean the cryptographic agent (**Identity** — Ed25519 key pair + DID + Handle) or the `identity` parameter on `AuthService` (which is just the handle string used as a vault namespace key). Prefer **Identity** for the full concept; say **handle** when referring to the string value.
