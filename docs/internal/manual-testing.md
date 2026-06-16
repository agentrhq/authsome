# Manual Testing Guide

This guide walks through the full CLI and UI surface. Run these after any significant change to verify that commands, flows, and output work end-to-end.

> **Output is always JSON.** Every command prints a JSON object wrapped as `{"v": 1, ...}` to stdout. There is no `--json` flag and no human-readable table mode. `--quiet` suppresses non-essential stderr messages only; it does not change the JSON on stdout.

## Prerequisites

```bash
uv pip install -e ".[dev]"
uv run authsome --version
```

> **Always point at localhost with an isolated home.** Every command in this guide must run against the local daemon and use a throwaway home directory so tests never touch your real credentials:
>
> ```bash
> export AUTHSOME_HOME=/tmp/authsome-test
> export AUTHSOME_BASE_URL=http://127.0.0.1:7998
> ```

> **Note on reset:** `rm -rf ~/.authsome` clears local state but does **not** stop a running daemon. If you reset while the daemon is running, `daemon stop` will say "No managed daemon record was found" and leave the process alive. Kill it manually first: `kill $(lsof -ti :7998)`, then reset.

---

## 1. Initialization & First-Run Claim

There is a single flow for every deployment (see ADR 0007): the first protected
command registers your Identity and then **blocks until you claim it in the
browser** with an email + password account. The first account created on a fresh
server becomes the **admin** Principal; every later account is a regular user.

```bash
# Kill daemon and start fresh (optional — skip to keep existing config)
kill $(lsof -ti :7998) 2>/dev/null; rm -rf $AUTHSOME_HOME

uv run authsome whoami
```

**Expected (first run):** the command prints a claim URL to stderr, opens it in a
browser, and blocks while polling:
```
Open this URL in your browser to claim this agent:
  http://127.0.0.1:7998/claim?token=claim_<token>
```

**Human action:**
1. The browser opens the claim page automatically (open the printed URL yourself if it doesn't, e.g. on a headless box).
2. Register with an email + password — or log in if the account already exists. The first account on a fresh server becomes the **admin** Principal.
3. Confirm that the displayed agent handle is yours.
4. The CLI unblocks and `whoami` prints your context. Subsequent commands reuse the accepted claim — no browser step.

**Expected (after claim):** a JSON object (`{"v": 1, ...}`) with key fields `authsome_version`, `home_directory`, `agent` (registered non-default agent handle), `principal_id`, `vault_id`, `did`, `registration_status`, `daemon_url`, `configured_encryption_mode`, `effective_encryption_source`, `encryption_backend`, `vault_status` (`OK`), `connected_providers_count` (`0`), `connected_providers` (`[]`), and `issues` (`[]`).

```bash
uv run authsome doctor
```

**Expected:** Exit code `0`; JSON `{"v": 1, "status": "ready", "checks": {"spec_version": "ok", "store": "ok", "identity": "ok", "providers": "ok", "connections": "ok", "vault": "ok", "integrity": "ok"}, "issues": [], "warnings": [...]}`. The `warnings` array is non-empty on a fresh install with no connections (e.g. "no active provider connections found"). A non-`ready` status exits `1`.

> **Tip:** `authsome onboard` performs register + claim and imports API keys from env in one step, printing a combined JSON payload.

---

## 2. Login — API Key

**Prerequisite (human):** Have a [Resend API key](https://resend.com/api-keys) ready.

```bash
uv run authsome login resend
```

**Expected:** JSON with `status: "started"`, `provider: "resend"`, `connection: "default"`, `record_status: "waiting_for_user"`, a `session_id`, and an `auth_url` pointing at the daemon input page. The URL opens in a browser automatically.

**Human action:**
1. Open the printed `auth_url` in a browser (it opens automatically if a browser is available)
2. Paste your Resend API key into the field and click **Submit**
3. The browser confirms success and redirects to the connections page

```bash
uv run authsome provider list
```

**Expected:** `resend` appears under `bundled` with a non-empty `connections` array whose entry shows `status: "connected"`.

```bash
# Verify the Resend API call succeeds through the proxy
uv run authsome run --quiet curl -s https://api.resend.com/domains
```

**Expected:** JSON from Resend containing an `object: "list"` and a `data` array of your verified domains. No proxy log noise (suppressed by `--quiet`).

---

## 3. Login — OAuth2 PKCE

**Prerequisite (human):** A GitHub account. Optionally, a [GitHub OAuth App](https://github.com/settings/developers) with Client ID and Secret — leave both blank to use the public PKCE flow.

```bash
uv run authsome login github
```

**Expected:** JSON with `status: "started"`, a `session_id`, and an `auth_url`. The URL opens in a browser automatically.

**Human action:**
1. Open the printed `auth_url` in a browser
2. Optionally enter your GitHub OAuth App Client ID and Secret (leave blank for the public flow)
3. Click **Continue** — the browser redirects to `https://github.com/login/oauth/authorize?...`
4. Click **Authorize** on GitHub; the daemon captures the callback

```bash
uv run authsome provider list
```

**Expected:** `github` shows a connection with `status: "connected"`.

---

## 4. Login — OAuth2 DCR-PKCE (Notion)

**Prerequisite (human):** A Notion account.

```bash
uv run authsome login notion_dcr
```

**Expected:** JSON with `status: "started"` and an `auth_url`. The URL opens in a browser automatically. The flow performs Dynamic Client Registration before the OAuth redirect.

```bash
uv run authsome provider list
```

**Expected:** `notion_dcr` shows a connection with `status: "connected"`.

---

## 5. Login — Device Code (headless)

**Prerequisite (human):** A GitHub account. No OAuth App needed — uses GitHub's public device code flow.

```bash
uv run authsome login github --flow device_code
```

**Expected:** JSON with `status: "started"`, a `session_id`, and an `auth_url`.

**Human action:**
1. Open the printed `auth_url` in a browser
2. Leave **Client ID** blank; click **Continue**
3. The page shows a verification URL and a user code
4. Open the verification URL, enter the user code, and authorize on GitHub

```bash
uv run authsome provider list
```

**Expected:** `github` shows a connection with `status: "connected"`.

---

## 6. Login — Browser Cookie Flow (LinkedIn)

**Prerequisite (human):** A LinkedIn account already logged in to Chrome.

```bash
uv run authsome login linkedin-browser
```

**Expected:** The CLI reads Chrome's cookie database. If valid session cookies are found, login completes without opening a browser; otherwise a browser window opens to the LinkedIn login page and the CLI polls until cookies appear.

```bash
uv run authsome provider list
```

**Expected:** `linkedin-browser` shows a connection with `status: "connected"`.

---

## 7. Provider List

```bash
uv run authsome provider list
```

**Expected:** JSON with `bundled` and `custom` arrays. Each provider entry has `name`, `display_name`, `auth_type`, `source`, and a `connections` array; connected providers have a non-empty `connections` array with `connection_name`, `is_default`, `auth_type`, `status`, and (for OAuth) `scopes`/`expires_at`.

---

## 8. Connection Inspect

```bash
uv run authsome connections inspect github
```

**Expected:** The connection record as JSON with sensitive fields redacted (`***REDACTED***`). There is no flag to reveal secrets via the CLI; inspect is always redacted.

```bash
uv run authsome connections inspect github --field status
```

**Expected:** `{"v": 1, "status": "connected"}`.

```bash
uv run authsome connections inspect github --field scopes
```

**Expected:** `{"v": 1, "scopes": [...]}` — the granted scope list.

```bash
uv run authsome connections inspect github --connection default
```

**Expected:** Same record, scoped to the named connection. An unknown `--field` returns `{"error": "FieldNotFound", ...}` and exits `1`.

---

## 9. Provider Inspect

```bash
uv run authsome provider inspect github
```

**Expected:** Full provider definition (URLs, flow config, scopes) as JSON; a `connections` array lists active connections.

```bash
uv run authsome provider inspect resend
```

**Expected:** Provider definition with an `api_key` config block and a `connections` array.

---

## 10. Proxy Run

**Prerequisite:** `github` must be connected (complete §3 first).

```bash
# Verify the GitHub whoami call succeeds through the proxy
uv run authsome run --quiet curl -s https://api.github.com/user
```

**Expected:** JSON response from GitHub containing a `login` field with your GitHub username. No proxy log noise (suppressed by `--quiet`). The subprocess exit code is propagated.

---

## 11. Log

```bash
uv run authsome log
```

**Expected:** JSON with `v`, `log_file` path, and an `entries` array of parsed audit event objects (each with `timestamp`, `event`, `provider`, `status`). The audit log is backed by SQLite. Empty `entries` on a fresh install.

---

## 12. Connection Management

```bash
uv run authsome connections set-default github default
```

**Expected:** `{"v": 1, "status": "ok", "provider": "github", "default_connection": "default"}`.

---

## 13. Custom Provider Registration

```bash
cat > /tmp/test-provider.json << 'EOF'
{
  "name": "test-custom",
  "display_name": "Test Custom",
  "auth_type": "api_key",
  "flow": "api_key",
  "api_key": {
    "header_name": "X-Test-Key"
  }
}
EOF

uv run authsome provider register /tmp/test-provider.json
```

**Expected:** `{"v": 1, "status": "registered", "provider": "test-custom", "warnings": [...]}`. No `api_url` means no reachability warning. Registering a provider requires the **admin** Principal (the first/only account in a fresh install is admin).

```bash
uv run authsome provider inspect test-custom
```

**Expected:** Provider definition printed as JSON; `connections` is empty.

```bash
uv run authsome provider list   # then look for the test-custom entry under "custom"
```

**Expected:** `test-custom` appears in the `custom` array with an empty `connections` array.

```bash
uv run authsome provider remove test-custom
```

**Expected:** `{"v": 1, "status": "removed", "provider": "test-custom"}`.

```bash
uv run authsome provider list   # confirm test-custom is gone from "custom"
```

**Expected:** No `test-custom` entry.

---

## 14. Logout and Revoke

```bash
# Logout removes the local connection record only
uv run authsome logout github
uv run authsome provider list   # github connection gone

# Re-login
uv run authsome login github

# Revoke deletes all stored connections/secrets for the provider (admin only)
uv run authsome provider revoke github
uv run authsome provider list   # github connection gone
```

**Expected:** `logout` → `{"status": "logged_out", ...}`; `revoke` → `{"status": "revoked", "provider": "github"}`. A non-admin Principal is rejected with an `OperationNotAllowedError`.

---

## 15. Agents

```bash
uv run authsome agent create --handle work
```

**Expected:** `{"v": 1, "status": "created", "agent": "work", "did": "did:key:...", ...}`. A new local Ed25519 keypair; the next protected command for this agent triggers its own browser claim.

```bash
uv run authsome agent use work
uv run authsome whoami   # agent reflects "work" (claim required on first use)
```

**Expected:** `agent use` -> `{"status": "active", "agent": "work", ...}`.

---

## 16. Daemon

```bash
uv run authsome daemon status
```

**Expected:** JSON showing `running: true`, health checks all `ok`, PID, and log file path. The `health` block includes `version` and `encryption_backend`.

```bash
uv run authsome daemon stop
uv run authsome daemon status   # running: false
```

**Expected:** `{"status": "stopped", "message": "..."}`; `running: false` after stop.

> **Note:** If no PID record exists (e.g. after `rm -rf ~/.authsome`), `daemon stop` falls back to finding the process by port and kills it.

```bash
uv run authsome daemon start
uv run authsome daemon status   # running: true
```

**Expected:** `{"status": "started", ...}`; `running: true` after start.

```bash
uv run authsome daemon restart
uv run authsome daemon logs -n 20
```

**Expected:** `restart` → `{"status": "restarted", ...}`; `logs` → JSON with `log_file` and the last 20 daemon log lines.

```bash
# Foreground mode — use a separate terminal; Ctrl-C to stop
uv run authsome daemon serve
```

**Expected:** The daemon starts in the foreground; log lines stream to stdout. No JSON response.

### Idempotency

```bash
# Starting an already-running daemon
uv run authsome daemon start
```

**Expected:** `{"status": "already_running", "message": "..."}` — no second process spawned.

```bash
# Stopping when nothing is running
uv run authsome daemon stop
uv run authsome daemon stop
```

**Expected (second stop):** `{"status": "not_stopped", "message": "..."}` — no error.

---

## 17. Dashboard UI

The dashboard is a Next.js static app served by the daemon at `http://127.0.0.1:7998/`.

Open `http://127.0.0.1:7998/` in a browser.

**Human action:**
1. Register with a new email + password (the first account becomes admin) or log in with an existing account.
2. Connect a provider using the **Connect** button:
   - API-key provider: paste the key and submit — should land on the connections page showing `connected`
   - OAuth provider: complete the browser redirect — on callback the UI should redirect back to the connections page
   - Device-code provider: the device code page shows the user code and verification URL
3. Verify the post-login redirect: after any successful connect the browser lands on the connections page (not the success message page).
4. Click **Logout** — the UI redirects back to the login page and the session cookie is cleared.

---

## 18. Global Flags

```bash
# Quiet: suppress non-essential stderr messages (JSON stdout unchanged)
uv run authsome --quiet provider list
```

**Expected:** The same provider JSON on stdout; informational/stderr chatter suppressed.

```bash
# No color: disable ANSI colors
uv run authsome --no-color provider list
```

**Expected:** Same JSON without ANSI color codes.

```bash
# Verbose: DEBUG logging to stderr
uv run authsome --verbose connections inspect github
```

**Expected:** DEBUG log lines on stderr in addition to the normal JSON stdout.

---

## 19. Error Handling

```bash
# Non-existent provider
uv run authsome login doesnotexist 2>&1; echo "exit: $?"
```

**Expected:** `ProviderNotFoundError`, exit code `4`.

```bash
uv run authsome provider inspect doesnotexist 2>&1; echo "exit: $?"
```

**Expected:** `ProviderNotFoundError`, exit code `4`.

```bash
uv run authsome logout doesnotexist 2>&1; echo "exit: $?"
```

**Expected:** `ProviderNotFoundError`, exit code `4`.

```bash
# Missing required argument
uv run authsome connections inspect 2>&1; echo "exit: $?"
```

**Expected:** Click usage error, exit code `2`.

```bash
# Inspect a disconnected provider
uv run authsome logout resend
uv run authsome connections inspect resend 2>&1; echo "exit: $?"
```

**Expected:** `ConnectionNotFoundError`, exit code `3`.

### Exit code reference

| Code | Exception |
|------|-----------|
| 1 | Generic / unclassified error |
| 2 | `AuthenticationFailedError`, `InputCancelledError` |
| 3 | `ConnectionNotFoundError` |
| 4 | `ProviderNotFoundError`, `OperationNotAllowedError` |
| 5 | `CredentialMissingError`, `TokenExpiredError`, `RefreshFailedError` |
| 6 | `ConnectionAlreadyExistsError` |
| 7 | `ProviderAlreadyRegisteredError` |
| 8 | `EndpointUnreachableError` |
| 9 | `DaemonUnavailableError` |

---

## Cleanup

```bash
uv run authsome daemon stop
rm -rf $AUTHSOME_HOME
```
