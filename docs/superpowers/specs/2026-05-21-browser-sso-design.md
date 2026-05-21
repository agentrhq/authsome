# Browser SSO Design

**Date:** 2026-05-21
**Status:** Approved

## Overview

Authsome currently supports `oauth2` (PKCE, device code, DCR-PKCE) and `api_key` flows. Neither works for services that require browser-based session authentication — where credentials live as cookies in a browser session rather than as OAuth2 tokens or API keys. X (Twitter) is the primary example: its internal API uses session cookies (`auth_token`, `ct0`) rather than an OAuth2 token endpoint accessible to third-party apps without a registered developer application.

Browser SSO fills this gap. It adds a new `auth_type = browser_sso` and `flow = browser_sso` that:

1. Opens a visible CloakBrowser window for one-time login (`authsome login <provider>`)
2. Extracts cookies and/or localStorage values per provider-defined rules
3. Stores extracted credentials in the Vault (encrypted at rest)
4. Validates stored credentials headlessly before every use (HTTP request to `validate_url`)
5. Injects multiple HTTP headers into proxied requests via `extra_headers` template rules

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Browser library | CloakBrowser (`pip install cloakbrowser`) | Drop-in Playwright replacement with source-level Chromium C++ stealth patches; passes X bot detection (0.9 reCAPTCHA v3 score, Cloudflare Turnstile) |
| Browser runtime | CLI-side only | CLI owns the visible browser (interactive); daemon owns the Vault. CloakBrowser is never needed in the daemon. |
| Credential storage | New `credentials: dict[str, str] \| None` field on `ConnectionRecord` | Explicit, type-safe, auditable. Marked `Sensitive()` for redaction. |
| Validation | HTTP GET to `validate_url`; 2xx = valid, 4xx = expired | No browser needed; daemon does this as a plain HTTP call |
| Refresh on expiry | Error: "credentials expired, run `authsome login <provider>`" | No local browser fallback. Authsome's model is explicit login. |
| Header injection | `extra_headers: dict[str, str]` with `${key}` template substitution | Handles both static values (bearer token) and dynamic values (cookie, ct0). Static values have no `${}`. |
| Bundled providers | `x-browser.json` alongside existing `x.json` (OAuth2 PKCE) | Both coexist. `x-browser` works for any user; `x` requires a Twitter developer app. |
| `validate_rule` | Not in v1 | `validate_url` HTTP status is sufficient for X. `validate_rule` can be added in v2 for services that return 200 with error bodies. |

## Schema Changes

### `enums.py`

```python
class AuthType(StrEnum):
    BROWSER_SSO = "browser_sso"   # new

class FlowType(StrEnum):
    BROWSER_SSO = "browser_sso"   # new
```

### `provider.py` — new models

```python
class ExtractRule(BaseModel):
    from_: Literal["cookies", "localStorage"] = Field(alias="from")
    as_: str = Field(alias="as")        # key name in credentials{}
    match: str                           # cookie name or localStorage key.
                                         # "*" = all cookies joined as "k=v; k=v" string.
                                         # Exact name (e.g. "ct0") = single cookie value.
    json_path: str | None = None         # dot-path for nested localStorage values

class BrowserSSOConfig(BaseModel):
    entry_url: str                       # CloakBrowser navigates here on login
    domains: list[str]                   # cookie capture scope
    validate_url: str | None = None      # GET this; 2xx = valid
    extract: list[ExtractRule]           # what to extract from browser
    extra_headers: dict[str, str] = {}   # headers injected by proxy; ${key} = credential lookup
    network_proxy: str | None = None     # socks5://host:port or http://host:port
    ttl: str | None = None               # max lifetime even if validate_url still passes (e.g. "30d")
    login_mode: Literal["auto", "visible", "headless"] = "auto"

# Added to ProviderDefinition:
browser_sso: BrowserSSOConfig | None = None
```

### `connection.py` — one new field

```python
class ConnectionRecord(BaseModel):
    # existing fields unchanged ...
    credentials: Annotated[dict[str, str] | None, Sensitive()] = None
    # ^ {"cookie": "...", "ct0": "...", "auth_token": "..."}
```

### `service.py` — guard + handler registration

```python
_VALID_FLOWS = {
    ...
    AuthType.BROWSER_SSO: {FlowType.BROWSER_SSO},
}

_FLOW_HANDLERS = {
    ...
    FlowType.BROWSER_SSO: BrowserSSOFlow,
}
```

## New Flow: `BrowserSSOFlow`

File: `src/authsome/auth/flows/browser_sso.py`

Implements `AuthFlow`. The flow has two phases driven by the existing `begin` / `resume` protocol:

### `begin()` — CLI-side browser launch

Called when the CLI sends `POST /auth/login`. The flow transitions the session to `waiting_for_user` and stores the provider config in `session.payload`. No browser is opened server-side.

The CLI receives `waiting_for_user` state and:
1. Fetches provider config (entry_url, domains, extract rules) from daemon
2. Launches `CloakBrowser` in visible mode (or headless if `login_mode = "headless"`)
3. Navigates to `entry_url`
4. Polls until cookies validate against `validate_url` (or user closes browser)
5. POSTs extracted `credentials: dict[str, str]` back to daemon as callback data

### `resume()` — credential storage

Called when the CLI POSTs callback data. The flow:
1. Builds a `ConnectionRecord` with `auth_type = browser_sso`, `status = connected`
2. Sets `record.credentials = callback_data["credentials"]`
3. Sets `record.expires_at` from `ttl` if configured
4. Returns `FlowResult(connection=record)`

### Validation (daemon, no browser)

Before returning credentials from the Vault, the daemon GETs `validate_url` with the stored `Cookie` header. Response:
- 2xx → credentials valid, proceed
- 4xx / network error → mark `status = expired`, raise `TokenExpiredError`

This validation runs inside `_get_access_token_from_record` / `_get_auth_headers_from_record` for the `BROWSER_SSO` auth type.

## Header Injection

`_get_auth_headers_from_record` for `browser_sso` evaluates `extra_headers` with template substitution:

```python
def _render_extra_headers(
    extra_headers: dict[str, str],
    credentials: dict[str, str],
) -> dict[str, str]:
    result = {}
    for header_name, template in extra_headers.items():
        value = re.sub(
            r"\$\{(\w[\w-]*)\}",
            lambda m: credentials.get(m.group(1), ""),
            template,
        )
        result[header_name] = value
    return result
```

- `"${cookie}"` → `credentials["cookie"]`
- `"Bearer AAAAAo..."` (no `${}`) → returned as-is

## Bundled Provider: `x-browser.json`

```json
{
  "schema_version": 1,
  "name": "x-browser",
  "display_name": "X (Twitter) — Browser SSO",
  "auth_type": "browser_sso",
  "flow": "browser_sso",
  "api_url": "regex:^(api\\.twitter\\.com|api\\.x\\.com|x\\.com|twitter\\.com)",
  "browser_sso": {
    "entry_url": "https://x.com/",
    "domains": ["x.com", "twitter.com"],
    "validate_url": "https://x.com/i/api/2/notifications/all.json?count=1",
    "extract": [
      { "from": "cookies", "as": "cookie",      "match": "*"          },
      { "from": "cookies", "as": "ct0",         "match": "ct0"        },
      { "from": "cookies", "as": "auth_token",  "match": "auth_token" }
    ],
    "extra_headers": {
      "Cookie":        "${cookie}",
      "x-csrf-token":  "${ct0}",
      "Authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA"
    },
    "ttl": "30d"
  },
  "export": {
    "env": {
      "cookie":     "X_COOKIE",
      "ct0":        "X_CT0",
      "auth_token": "X_AUTH_TOKEN"
    }
  }
}
```

## CLI Changes

### `authsome login x-browser`

New code path in CLI when the session `flow_type == "browser_sso"`:

1. Receive `waiting_for_user` response with provider config from daemon
2. Import `cloakbrowser` (fail fast with helpful message if not installed: `pip install cloakbrowser`)
3. Launch browser with `launch_persistent_context(user_data_dir=~/.authsome/browser-profiles/<provider>/, headless=False)`
4. Navigate to `entry_url`
5. Poll: GET `validate_url` with current page cookies until 2xx (or timeout after `visibleTimeout`)
6. Extract credentials per `extract` rules using Playwright cookie API (`context.cookies()`)
7. POST credentials to daemon callback endpoint
8. Browser closes

The `~/.authsome/browser-profiles/<provider>/` persistent context means the user only needs to log in once — subsequent `authsome login x-browser` runs can reuse the browser profile, potentially skipping the login form entirely.

### `authsome login x-browser --headless`

Runs in headless mode. Useful when the user knows the session is still alive in the persistent browser profile.

## Proxy Integration

No changes needed to the proxy routing or `router.py`. The `api_url` regex in the provider JSON already handles route matching. The only change is in `_get_auth_headers_from_record` to handle `auth_type = browser_sso` by calling `_render_extra_headers`.

## Dependencies

| Package | Where | Why |
|---|---|---|
| `cloakbrowser` | CLI (`pyproject.toml` optional dep or install extra) | Visible browser login, cookie extraction |

The daemon has zero new dependencies.

### Optional dependency strategy

Add `cloakbrowser` as an optional extra in `pyproject.toml`:

```toml
[project.optional-dependencies]
browser = ["cloakbrowser>=0.3"]
```

Install with: `uv tool install authsome[browser]`

If `cloakbrowser` is not installed and the user runs `authsome login <browser-sso-provider>`, the CLI prints:

```
Browser SSO requires the browser extra.
Install it with: uv tool install authsome[browser]
```

## Error Handling

| Scenario | Behaviour |
|---|---|
| `validate_url` returns 401/403 | Mark connection `expired`; surface `TokenExpiredError` with hint to re-run `authsome login` |
| `validate_url` network error | Log warning, return cached credentials (tolerate transient failures) |
| `cloakbrowser` not installed | CLI raises with install hint before starting session |
| Login timeout (user never logs in) | CLI cancels session; no credentials stored |
| Browser closed by user mid-login | CLI detects context close, cancels session |
| `ttl` exceeded | Treat as expired regardless of `validate_url` result |

## Testing

- Unit tests for `BrowserSSOFlow.resume()` — mock callback data, assert correct `ConnectionRecord` fields
- Unit tests for `_render_extra_headers()` — template substitution, missing key → empty string, no-template passthrough
- Unit tests for `BrowserSSOConfig` Pydantic validation — missing required fields, invalid `login_mode`
- Unit tests for `_get_auth_headers_from_record` with `browser_sso` auth type
- Unit tests for credential expiry path (validate_url mocked to 401)
- Integration test for `x-browser.json` loads correctly as a bundled provider
- CLI login flow tested with a mock CloakBrowser (monkeypatched) — no real browser in CI

## Files Changed

| File | Change |
|---|---|
| `src/authsome/auth/models/enums.py` | +2 enum values |
| `src/authsome/auth/models/provider.py` | +`ExtractRule`, +`BrowserSSOConfig`, +`browser_sso` field on `ProviderDefinition` |
| `src/authsome/auth/models/connection.py` | +`credentials` field on `ConnectionRecord` |
| `src/authsome/auth/flows/browser_sso.py` | New file — `BrowserSSOFlow` |
| `src/authsome/auth/service.py` | Register `BrowserSSOFlow` in `_VALID_FLOWS` and `_FLOW_HANDLERS`; handle `browser_sso` in `_get_auth_headers_from_record` |
| `src/authsome/auth/bundled_providers/x-browser.json` | New file — bundled X provider |
| `src/authsome/cli/main.py` (or helpers) | New CLI code path for `browser_sso` flow type |
| `src/authsome/auth/service.py` (`_export_connection_values`) | +`browser_sso` branch: export from `credentials` dict using `export.env` map |
| `pyproject.toml` | +`browser` optional extra with `cloakbrowser` |
| `tests/auth/test_browser_sso_flow.py` | New test file |
| `tests/auth/test_browser_sso_headers.py` | New test file |
