# Ubiquitous Language

## Architecture Layers

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Vault** | The secure credential store. Owns the master key and DiskStore-backed KV storage. Exposes a generic encrypted key-value interface (`get`/`put`/`delete`/`list`). Encrypts full record blobs at rest. Does not know about credential types or token lifecycle. | Store, keystore, secret store |
| **AuthLayer** | The authentication and credential lifecycle layer (`AuthService`, exported as `AuthLayer`). Owns OAuth flows, token refresh, login/logout/revoke. Receives Vault as a dependency. | Auth client, auth service |
| **CliRuntime** | The runtime wiring container assembled once per CLI invocation (`src/authsome/cli/context.py`). Holds a `RuntimeClient` (HTTP client for daemon requests) and a `ProxyRunner`. No business logic of its own. | Client, session, app, AuthsomeContext |
| **RuntimeClient** | The CLI's internal async HTTP client for daemon requests. Attaches PoP JWT headers to protected requests and manages identity bootstrapping. | Daemon client, HTTP client |
| **Sensitive** | A field annotation (`Annotated[str, Sensitive()]`) marking fields that contain secret values and must be redacted before display or logging. The `redact()` utility in `utils.py` inspects this annotation to replace values with `"***REDACTED***"`. | Secret field, encrypted field |

## Identity & Authentication

| Term | Definition | Aliases to avoid |
| --- | --- | --- |
| **Identity** | The cryptographic agent — an Ed25519 key pair, a `did:key` DID derived from the public key, and a human-readable Handle. Created locally by `authsome init`; the Handle/DID pair is registered with the daemon before any protected request. | User, account, actor |
| **Handle** | The human-readable name for an Identity (e.g., `brisk-boldly-clearly-1234`). Assigned at `init` time, registered with the daemon's Identity Registry, and used as the `sub` claim in every PoP JWT. Also serves as the Profile name for credential scoping. | Username, alias, profile name |
| **DID** | A `did:key` Ed25519 identifier derived deterministically from the Identity's public key. Encoded as `did:key:z<base58(0xed01 + raw_pubkey)>`. Appears as `iss` in PoP JWTs; the daemon verifies the signature against the public key embedded in the DID. SPIFFE URI support may be added in a future release. | Key ID, public key identifier |
| **PoP JWT** | A short-lived (60 s) Proof-of-Possession JWT signed with the Identity's Ed25519 private key. Bound to a specific HTTP request via `htm` (method), `htu` (path+query), and `body_sha256`. Claims: `iss` = DID, `sub` = Handle, `jti` for replay prevention. Sent as `Authorization: PoP <token>`. | Auth token, bearer token, signed request |
| **Identity Registry** | The daemon-owned authoritative mapping from Handle → DID, persisted at `~/.authsome/server/identity_registry.json`. A protected request is accepted only when the PoP JWT's `sub` is a registered Handle and the registry maps that Handle to the same DID as `iss`. | Identity store, key registry |
| **Provider** | An external service (GitHub, Google, OpenAI, etc.) identified by a unique name and described by a `ProviderDefinition` | Service, integration, app |
| **AuthType** | The authentication mechanism a provider uses — either `oauth2` or `api_key` | Auth method, auth strategy |
| **Flow** | The specific protocol executed to obtain credentials for a provider (PKCE, Device Code, DCR+PKCE, API Key) | Auth flow, login flow, grant type |
| **Connection** | A named, authenticated session binding a Profile to a Provider; holds credentials | Credential, token, session, auth |
| **ConnectionStatus** | The lifecycle state of a Connection: `connected`, `expired`, `revoked`, `invalid`, `not_connected` | Status, state |
| **Profile** | The credential namespace scoped by a Handle within the Vault. Store keys use the prefix `profile:<handle>:`. One Identity has exactly one Profile; they share the same name string (the Handle). | Environment, workspace, account |
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

- An **Identity** has exactly one **Profile**; both share the same name string (the **Handle**).
- A **Profile** contains zero or more **Connections**, each scoped to one **Provider**.
- A **Connection** is created by exactly one **Flow**; the FlowType is determined by the **ProviderDefinition**.
- A **ConnectionRecord** belongs to exactly one **Connection** and one **Profile**. Tokens are plaintext on the record; the **Vault** handles encryption transparently at write time.
- A **ProviderRegistry** resolves a provider name by checking local `~/.authsome/providers/` overrides before **BundledProviders**.
- The **Vault** encrypts full **ConnectionRecord** blobs using the master key it manages (file-based or OS keyring). The **AuthLayer** reads and writes records through the Vault without knowing the encryption details.
- An **AuthProxy** draws credentials from **Connections** in the active **Profile** via the **AuthLayer** and injects them as request headers.
- **CliRuntime** wires **RuntimeClient** and **ProxyRunner** together; the CLI creates one runtime per invocation via `ContextObj.initialize()`.
- **ClientCredentials** are server-scoped, not profile-scoped. A single `ProviderClientRecord` per Provider is shared by all Profiles on a server instance. `ConnectionRecord` tokens are always profile-scoped.
- A **PoP JWT** is issued by the CLI for each protected daemon request. The daemon validates the signature against the **DID** embedded in `iss`, then checks the **Identity Registry** to confirm `sub` (the Handle) maps to that same DID.

## Example dialogue

> **Dev:** "If I call `authsome login github`, does it create a new **Profile**?"
>
> **Domain expert:** "No — `login` adds a **Connection** to the currently active **Profile**. A **Profile** is created automatically if it doesn't exist. The `login` command runs the **Flow** specified in the GitHub **ProviderDefinition** and stores the result as a **ConnectionRecord** via the **Vault**."
>
> **Dev:** "So the **Connection** is what I query later to get the access token?"
>
> **Domain expert:** "Exactly. When you call `get_access_token`, the **AuthLayer** looks up the **ConnectionRecord** for that **Provider** + **Profile** combination through the **Vault** (which decrypts transparently) and returns the plaintext token."
>
> **Dev:** "And if the token is expired, does it auto-refresh?"
>
> **Domain expert:** "Yes — the **ConnectionStatus** will show `expired`, and the **ConnectionRecord** holds the `refresh_token` so the **AuthLayer** can exchange it without re-running the **Flow**. The outcome is a new **ConnectionRecord** with updated tokens and `status = connected`."
>
> **Dev:** "What if I need to connect to two GitHub accounts?"
>
> **Domain expert:** "Use two **Profiles** — one per identity context. Each **Profile** has its own scoped keys in the **Vault**, so the two **Connections** to the `github` **Provider** are completely isolated."

## Flagged ambiguities

- **"client"** can mean the `RuntimeClient` (the CLI's internal HTTP client for daemon requests) or `ClientCredentials` (the OAuth2 `client_id`/`client_secret` pair). Use **RuntimeClient** for the former and **ClientCredentials** / `ProviderClientRecord` for the latter.
- **"flow"** is used as both a `FlowType` enum value (a string like `"pkce"`) and an `AuthFlow` instance (the object that executes the protocol). Distinguish by saying **flow type** for the enum and **flow** or **flow handler** for the runtime object.
- **"provider"** can mean a provider name string (`"github"`), a `ProviderDefinition` object, or a row in the ProviderRegistry. Prefer **Provider** (capitalized) for the concept, **ProviderDefinition** for the JSON schema, and **provider name** for the identifier string.
- **"credential"** was used loosely in early documentation to mean both a **Connection** (the full authenticated session) and a specific secret (the token). Use **Connection** for the session and **access token** / **API key** for the individual secret values.
- **"identity"** can mean the cryptographic agent (**Identity** — Ed25519 key pair + DID + Handle) or the `identity` parameter on `AuthService` (which is just the handle string used as a vault namespace key). Prefer **Identity** for the full concept; say **handle** when referring to the string value.
