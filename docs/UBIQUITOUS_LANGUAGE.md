# Ubiquitous Language

## Architecture Layers

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Vault** | A named credential store owned by exactly one Principal, identified by an opaque **VaultId**. Encrypts full record blobs at rest. All credential store keys are prefixed `vault:<vault_id>:...`. Does not know about OAuth or token lifecycle — that is AuthService's job. | Store, keystore, secret store, profile store |
| **AuthLayer** | The authentication and credential lifecycle layer (`AuthService`, exported as `AuthLayer`). Owns OAuth flows, token refresh, login/logout/revoke. Receives Vault, identity handle, principal_id, and vault_id as dependencies. | Auth client, auth service |
| **CliRuntime** | The runtime wiring container assembled once per CLI invocation (`src/authsome/cli/context.py`). Holds a `RuntimeClient` (HTTP client for daemon requests) and a `ProxyRunner`. No business logic of its own. | Client, session, app, AuthsomeContext |
| **RuntimeClient** | The CLI's internal async HTTP client for daemon requests. Attaches PoP JWT headers to protected requests and manages identity bootstrapping. | Daemon client, HTTP client |
| **Sensitive** | A field annotation (`Annotated[str, Sensitive()]`) marking fields that contain secret values and must be redacted before display or logging. The `redact()` utility in `utils.py` inspects this annotation to replace values with `"***REDACTED***"`. | Secret field, encrypted field |
| **StorageSubstrate** | The concrete `AsyncKeyValue` backend where records physically live, such as `DiskStore`, `PostgreSQLStore`, or `MemoryStore`. In local mode, Client and Server may share one substrate. | Store, database, filesystem |
| **StorageNamespace** | A prefixed collection/key space over a StorageSubstrate that defines ownership, such as `client/*`, `server/*`, or `vault/*`. Shared substrate does not imply shared namespace or shared write authority. | Folder, bucket, table |
| **SecretSource** | A source for root key material or signing key material, resolved in priority order: environment, OS keyring, then local fallback. SecretSources hold keys; StorageSubstrates hold records. | Key store, secret store |
| **Repository** | A domain API over a StorageNamespace. It owns key naming, model serialization, and invariants for one domain concept while depending on `AsyncKeyValue` by composition. | DAO, model manager |

## Identity & Authentication

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Identity** | The cryptographic agent — an Ed25519 key pair, a `did:key` DID derived from the public key, and a human-readable Handle. Created locally by `authsome init`; the Handle/DID pair is registered with the daemon before any protected request. Identity is not a credential namespace — credentials are scoped to a Vault, not to an Identity. | User, account, actor, profile |
| **Handle** | The human-readable name for an Identity (e.g., `brisk-boldly-clearly-1234`). Assigned at `init` time, registered with the daemon's Identity Registry, and used as the `sub` claim in every PoP JWT. | Username, alias, profile name |
| **DID** | A `did:key` Ed25519 identifier derived deterministically from the Identity's public key. Encoded as `did:key:z<base58(0xed01 + raw_pubkey)>`. Appears as `iss` in PoP JWTs; the daemon verifies the signature against the public key embedded in the DID. | Key ID, public key identifier |
| **PoP JWT** | A short-lived (60 s) Proof-of-Possession JWT signed with the Identity's Ed25519 private key. Bound to a specific HTTP request via `htm` (method), `htu` (path+query), and `body_sha256`. Claims: `iss` = DID, `sub` = Handle, `jti` for replay prevention. Sent as `Authorization: PoP <token>`. | Auth token, bearer token, signed request |
| **Identity Registry** | The daemon-owned authoritative mapping from Handle → DID, persisted at `~/.authsome/server/identity_registry.json`. A protected request is accepted only when the PoP JWT's `sub` is a registered Handle and the registry maps that Handle to the same DID as `iss`. | Identity store, key registry |
| **Principal** | A non-cryptographic logical partition (human or team) that owns Vaults and performs OAuth authorization. Identified by an opaque **PrincipalId** (e.g., `principal_abc123def456`). Has no cryptographic key of its own. Every Identity registers under exactly one Principal via an **IdentityClaimRecord**. | User, account, team, workspace |
| **PrincipalId** | An opaque stable identifier for a Principal (e.g., `principal_abc123def456`). Never the email or handle — those can change; the PrincipalId cannot. | Principal handle, principal name |
| **VaultId** | An opaque stable identifier for a Vault (e.g., `vault_a1b2c3d4e5f6`). Used directly as the storage key segment: `vault:<vault_id>:...`. Stable across ownership and naming changes. | Vault name, vault handle |
| **VaultHandle** | A human-readable name for a Vault (e.g., `default`). Used in UIs and CLI output; the VaultId is authoritative in storage. | Vault name, vault id |
| **IdentityClaimRecord** | The binding from an Identity (Handle) to a Principal (PrincipalId) with a lifecycle state (ClaimStatus). Created when an Identity registers with `authsome init --email`. Vault access is gated until the claim is accepted. | Identity registration, claim |
| **ClaimStatus** | The lifecycle state of an IdentityClaimRecord: `pending` (awaiting acceptance), `accepted` (full vault access), `rejected` (access denied). | Claim state, identity state |
| **PrincipalVaultBindingRecord** | The server-owned record that binds a Principal to a Vault. Has `is_default` flag. A Principal may have multiple Vaults; the server resolves the default before constructing AuthService. | Principal vault, vault binding |
| **ActiveIdentity** | Client-owned selection of which Identity signs outgoing protected requests. Stored in client config as `active_identity`. Must not be mirrored into server-owned storage. | Active profile, default profile |
| **Provider** | An external service (GitHub, Google, OpenAI, etc.) identified by a unique name and described by a `ProviderDefinition`. | Service, integration, app |
| **AuthType** | The authentication mechanism a provider uses — either `oauth2` or `api_key`. | Auth method, auth strategy |
| **Flow** | The specific protocol executed to obtain credentials for a provider (PKCE, Device Code, DCR+PKCE, API Key). | Auth flow, login flow, grant type |
| **Connection** | A named, authenticated session binding a Vault to a Provider; holds credentials. | Credential, token, session, auth |
| **ConnectionStatus** | The lifecycle state of a Connection: `connected`, `expired`, `revoked`, `invalid`, `not_connected`. | Status, state |
| ~~**Profile**~~ | *Retired.* Credentials were previously scoped by `profile:<handle>:...`. That namespace is replaced by `vault:<vault_id>:...`. Use **Vault** and **Principal** instead. | — |
| **Scope** | An OAuth2 permission requested from a Provider during a Flow. | Permission, role |

## Provider Configuration

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **ProviderDefinition** | The complete JSON schema describing a provider's AuthType, Flow, OAuth endpoints, and export mapping. | Provider config, provider spec |
| **BundledProvider** | A ProviderDefinition shipped inside the library package. | Built-in provider, default provider |
| **ProviderRegistry** | The system that resolves a provider name to its ProviderDefinition, checking local overrides before bundled definitions. | Provider loader, provider resolver |
| **OAuthConfig** | The OAuth2-specific section of a ProviderDefinition (authorization URL, token URL, PKCE support, etc.). | OAuth settings |
| **ApiKeyConfig** | The API-key-specific section of a ProviderDefinition (header name and prefix). | API key settings |
| **ClientCredentials** | The OAuth2 `client_id` and `client_secret` configured for a Provider, stored in a `ProviderClientRecord`. | OAuth client, app credentials |

## Storage & Credentials

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **IdentityMetadata** | Client-owned record for a local Identity. Fields: `handle`, `did`, `registered` (client-side cache of registration state), `created_at`, `updated_at`. The daemon never treats this as authoritative. | Identity record, key metadata |
| **IdentityRegistration** | Server-owned record in the Identity Registry binding a Handle to a DID. Fields: `handle`, `did`, `created_at`, `updated_at`. Authoritative for PoP JWT validation. Does not contain `registered`, `active_identity`, or private key material. | Registry entry, daemon identity |
| **ConnectionRecord** | The persisted credential record for a Connection: plaintext tokens or API key (encrypted at rest by the Vault), scopes, expiry, and account info. `schema_version = 2`. Contains `principal_id` and `vault_id` for ownership context. | Token record, credential record |
| **ProviderMetadataRecord** | Non-secret per-vault record tracking which Connections exist for a Provider and which is the default. | Provider metadata |
| **ProviderStateRecord** | Transient per-vault record tracking the last refresh attempt and any errors for a Provider. | Provider state |
| **AccountInfo** | The identity fields (id, label) returned by a Provider and stored on a ConnectionRecord. | User info, identity |
| **ClientCredentials** | The OAuth2 `client_id` and `client_secret` for a Provider, stored in a `ProviderClientRecord` at server scope (key: `server:<provider>:client`). Shared across all Vaults and Principals on a server instance — they represent the OAuth application registration, not a user. | User credentials, per-vault client |
| ~~**EncryptedField**~~ | *Removed.* No longer part of the public model layer. Encryption is handled entirely within the Vault. Tokens are stored as plaintext `str` on `ConnectionRecord` and marked with the `Sensitive` annotation for display safety. | — |
| ~~**CredentialStore**~~ | *Deprecated.* Internal implementation detail of the Vault. Do not use in documentation or code outside `vault/`. | — |
| ~~**CryptoBackend**~~ | *Deprecated.* Internal implementation detail of the Vault. Do not use in documentation or code outside `vault/`. | — |
| ~~**ProfileMetadata**~~ | *Removed.* Profile is retired; no separate metadata record exists. | — |

## Flows

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **PKCE Flow** | Browser-based OAuth2 authorization code grant with PKCE; spins up a local callback server. | OAuth flow, browser flow |
| **Device Code Flow** | Headless OAuth2 via device authorization endpoint; polls until the user authorizes on another device. | Headless flow, device flow |
| **DCR PKCE Flow** | Dynamic Client Registration followed immediately by a PKCE Flow; used when providers require per-client registration. | Dynamic registration flow |
| **API Key Flow** | Collects an API key from the user via a Browser Bridge and stores it as a ConnectionRecord. | Key flow |
| **Browser Bridge** | A short-lived local HTTP server that presents a secure form to collect secrets (API keys) from the user interactively. | Secure input, form server |

## Proxy

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **AuthProxy** | A local mitmproxy-based HTTP proxy that intercepts outgoing requests and injects auth headers from active Connections. In local mode, unmatched requests pass through unchanged (ADR-0003). | Proxy, HTTP proxy |
| **RunningProxy** | A handle to an AuthProxy running in a background thread, with a `shutdown()` method. | Proxy handle, proxy instance |

## Relationships

- An **Identity** is a cryptographic agent. It does not own credentials directly.
- An **Identity** claims a **Principal** via an **IdentityClaimRecord**. The claim must be accepted (ClaimStatus = `accepted`) before vault access is granted.
- A **Principal** owns one or more **Vaults** via **PrincipalVaultBindingRecords**. The daemon resolves the default Vault before constructing AuthService.
- A **Vault** contains zero or more **Connections**, each scoped to one **Provider**.
- Multiple Identities may share one Vault (they all claim the same Principal and the binding points to that Vault).
- A **Connection** is created by exactly one **Flow**; the FlowType is determined by the **ProviderDefinition**.
- A **ConnectionRecord** belongs to exactly one **Connection** and one **Vault**. Tokens are plaintext on the record; the **Vault** handles encryption transparently at write time.
- A **ProviderRegistry** resolves a provider name by checking local `~/.authsome/providers/` overrides before **BundledProviders**.
- The **Vault** encrypts full **ConnectionRecord** blobs using the master key it manages (file-based or OS keyring). The **AuthLayer** reads and writes records through the Vault without knowing the encryption details.
- An **AuthProxy** draws credentials from **Connections** in the active **Vault** via the **AuthLayer** and injects them as request headers.
- **CliRuntime** wires **RuntimeClient** and **ProxyRunner** together; the CLI creates one runtime per invocation via `ContextObj.initialize()`.
- **ClientCredentials** are server-scoped, not vault-scoped. A single `ProviderClientRecord` per Provider is shared by all Vaults and Principals on a server instance. `ConnectionRecord` tokens are always vault-scoped.
- A **PoP JWT** is issued by the CLI for each protected daemon request. The daemon validates the signature against the **DID** embedded in `iss`, then checks the **Identity Registry** to confirm `sub` (the Handle) maps to that same DID.
- Client and Server may share a **StorageSubstrate** in local mode, but they do not share a **StorageNamespace** or ownership authority. Remote Server storage must never contain client Identity private keys; client signing keys resolve only from client-side **SecretSources**.

## Example dialogue

> **Dev:** "If I call `authsome login github`, does it create a new **Vault**?"
>
> **Domain expert:** "No — `login` adds a **Connection** to the currently active **Vault**. The active Vault is resolved at startup from the **PrincipalVaultBindingRegistry** using the Identity's **PrincipalId**. The `login` command runs the **Flow** specified in the GitHub **ProviderDefinition** and stores the result as a **ConnectionRecord** inside the Vault."
>
> **Dev:** "So the **Connection** is what I query later to get the access token?"
>
> **Domain expert:** "Exactly. When you call `get_access_token`, the **AuthLayer** looks up the **ConnectionRecord** for that **Provider** + **VaultId** combination through the **Vault** (which decrypts transparently) and returns the plaintext token."
>
> **Dev:** "And if the token is expired, does it auto-refresh?"
>
> **Domain expert:** "Yes — the **ConnectionStatus** will show `expired`, and the **ConnectionRecord** holds the `refresh_token` so the **AuthLayer** can exchange it without re-running the **Flow**. The outcome is a new **ConnectionRecord** with updated tokens and `status = connected`."
>
> **Dev:** "What if I need two agents to share the same GitHub account?"
>
> **Domain expert:** "Put them both under the same **Principal** and point them at the same **Vault**. Each agent has its own cryptographic **Identity** but claims the same Principal; the **PrincipalVaultBindingRecord** tells the server which Vault to use, so both agents share the same **Connections**."

## Flagged ambiguities

- **"client"** can mean the `RuntimeClient` (the CLI's internal HTTP client for daemon requests) or `ClientCredentials` (the OAuth2 `client_id`/`client_secret` pair). Use **RuntimeClient** for the former and **ClientCredentials** / `ProviderClientRecord` for the latter.
- **"flow"** is used as both a `FlowType` enum value (a string like `"pkce"`) and an `AuthFlow` instance (the object that executes the protocol). Distinguish by saying **flow type** for the enum and **flow** or **flow handler** for the runtime object.
- **"provider"** can mean a provider name string (`"github"`), a `ProviderDefinition` object, or a row in the ProviderRegistry. Prefer **Provider** (capitalized) for the concept, **ProviderDefinition** for the JSON schema, and **provider name** for the identifier string.
- **"credential"** was used loosely in early documentation to mean both a **Connection** (the full authenticated session) and a specific secret (the token). Use **Connection** for the session and **access token** / **API key** for the individual secret values.
- **"identity"** can mean the cryptographic agent (**Identity** — Ed25519 key pair + DID + Handle) or the `identity` parameter on `AuthService` (which is just the handle string carried for audit context). Prefer **Identity** for the full concept; say **handle** when referring to the string value.
- **"vault"** can refer to the `Vault` class (the encrypted KV store implementation) or a **Vault** record (the first-class entity with a VaultId). Distinguish by context; use **VaultId** when referring to the storage namespace key.
