# Manual Testing Guide

This guide walks through the full CLI surface. Run these after any significant change to verify that commands, flows, and output work end-to-end.

> **Output is always JSON.** Every command prints a JSON object wrapped as `{"v": 1, ...}` to stdout. There is no `--json` flag and no human-readable table mode. `--quiet` suppresses non-essential stderr messages only; it does not change the JSON on stdout.

## Prerequisites

```bash
uv pip install -e ".[dev]"
uv run authsome --version
```

> **Note on reset:** `rm -rf ~/.authsome` clears local state but does **not** stop a running daemon. If you reset while the daemon is running, `daemon stop` will say "No managed daemon record was found" and leave the process alive. Kill it manually first: `kill $(lsof -ti :7998)`, then reset.

---

## 1. Initialization & First-Run Claim

There is a single flow for every deployment (see ADR 0007): the first protected
command registers your Identity and then **blocks until you claim it in the
browser** with an email + password account. The first account created on a fresh
server becomes the **admin** Principal; every later account is a regular user.

```bash
# Kill daemon and start fresh (optional — skip to keep existing config)
kill $(lsof -ti :7998) 2>/dev/null; rm -rf ~/.authsome

uv run authsome whoami
```

**Expected (first run):** the command prints a claim URL to stderr, opens it in a
browser, and blocks while polling:
```
Open this URL in your browser to register and claim this identity:
  http://127.0.0.1:7998/claim/claim_<token>
```

**Human action:**
1. The browser opens the claim page automatically (open the printed URL yourself if it doesn't, e.g. on a headless box).
2. Register with an email + password — or log in if the account already exists. The first account on a fresh server becomes the **admin** Principal.
3. Confirm that the displayed identity handle is yours.
4. The CLI unblocks and `whoami` prints your context. Subsequent commands reuse the accepted claim — no browser step.

**Expected (after claim):** a JSON object (`{"v": 1, ...}`) with key fields `home_directory`, `profile` (registered non-default identity handle), `principal_id`, `vault_id`, `did`, `registration_status`, `daemon_url`, `encryption_backend`, `vault_status` (`OK`), and `connected_providers_count` (`0`).

```bash
uv run authsome doctor
```

**Expected:** Exit code `0`; JSON `{"v": 1, "status": "ready", "checks": {"spec_version": "ok", "store": "ok", "identity": "ok", "providers": "ok", "connections": "ok", "vault": "ok", "integrity": "ok"}, "issues": [], "warnings": [...]}`. The `warnings` array is non-empty on a fresh install with no connections (e.g. "no active provider connections found"). A non-`ready` status exits `1`.

> **Tip:** `authsome init` performs the same register + claim flow explicitly and prints an `{"status": "initialized", ...}` payload.

---

## 2. Login — API Key

**Prerequisite (human):** Have a [Resend API key](https://resend.com/api-keys) ready.

```bash
uv run authsome login resend
```

**Expected:** JSON with `status: "started"`, `provider: "resend"`, `connection: "default"`, a `session_id`, and an `auth_url` pointing at the daemon input page. The URL opens in a browser automatically.

**Human action:**
1. Open the printed `auth_url` in a browser (it opens automatically if a browser is available)
2. Paste your Resend API key into the field and click **Submit**
3. The browser confirms success

```bash
uv run authsome provider list
```

**Expected:** `resend` appears under `bundled` with a non-empty `connections` array whose entry shows `status: "connected"`.

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

## 4. Login — Device Code (headless)

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

## 5. Provider List

```bash
uv run authsome provider list
```

**Expected:** JSON with `bundled` and `custom` arrays. Each provider entry has `name`, `display_name`, `auth_type`, `source`, and a `connections` array; connected providers have a non-empty `connections` array with `connection_name`, `is_default`, `status`, and (for OAuth) `scopes`/`expires_at`.

---

## 6. Connection Inspect

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

## 7. Provider Inspect

```bash
uv run authsome provider inspect github
```

**Expected:** Full provider definition (URLs, flow config, scopes) as JSON; a `connections` array lists active connections.

```bash
uv run authsome provider inspect resend
```

**Expected:** Provider definition with an `api_key` config block and a `connections` array.

---

## 8. Proxy Run

**Prerequisite:** `github` must be connected (complete §3 first).

```bash
# Verify the GitHub whoami call succeeds through the proxy
uv run authsome run --quiet curl -s https://api.github.com/user
```

**Expected:** JSON response from GitHub containing a `login` field with your GitHub username. No proxy log noise (suppressed by `--quiet`). The subprocess exit code is propagated.

---

## 9. Log

```bash
uv run authsome log
```

**Expected:** JSON with `v`, `log_file` path, and an `entries` array of parsed audit event objects (each with `timestamp`, `event`, `provider`, `status`). Empty `entries` on a fresh install.

```bash
uv run authsome log -n 5
```

**Expected:** Same shape, limited to the last 5 audit entries.

```bash
uv run authsome log --raw -n 10
```

**Expected:** JSON with `log_file` and an `entries` array containing the last 10 raw client debug log lines (loguru format).

---

## 10. Connection Management

```bash
uv run authsome connections set-default github default
```

**Expected:** `{"v": 1, "status": "ok", "provider": "github", "default_connection": "default"}`.

---

## 11. Custom Provider Registration

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
# Register again with --force to overwrite, and --yes to skip the confirmation prompt
uv run authsome provider register /tmp/test-provider.json --force --yes
```

**Expected:** Re-registers without error; `status: "registered"`.

```bash
uv run authsome provider remove test-custom
```

**Expected:** `{"v": 1, "status": "removed", "provider": "test-custom"}`.

```bash
uv run authsome provider list   # confirm test-custom is gone from "custom"
```

**Expected:** No `test-custom` entry.

---

## 12. Logout and Revoke

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

## 13. Scan (env import)

```bash
# Report drift between env vars and stored connections (does not modify state)
uv run authsome scan
```

**Expected:** JSON with `connection`, `import: false`, `configured_count`, `imported_count: 0`, and a `results` array describing per-provider drift status (`env_only`, `authsome_only`, `env_and_authsome_match`, `both_missing`, etc.). `scan` rejects `--quiet`.

```bash
# Import detected API keys from env without prompting
uv run authsome scan --import
```

**Expected:** `import: true` with `imported_count` reflecting newly imported keys; matching keys are reported as `skipped_unchanged`.

---

## 14. Profiles

```bash
uv run authsome profile create --handle work
```

**Expected:** `{"v": 1, "status": "created", "profile": "work", "did": "did:key:...", ...}`. A new local Ed25519 keypair; the next protected command for this profile triggers its own browser claim.

```bash
uv run authsome profile use work
uv run authsome whoami   # profile reflects "work" (claim required on first use)
```

**Expected:** `profile use` → `{"status": "active", "profile": "work", ...}`.

---

## 15. Daemon

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

---

## 16. Global Flags

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

## 17. Error Handling

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

**Expected:** Usage error, exit code `2`.

```bash
# Inspect a disconnected provider
uv run authsome logout resend
uv run authsome connections inspect resend 2>&1; echo "exit: $?"
```

**Expected:** `ConnectionNotFoundError`, exit code `3`.

---

## Cleanup

```bash
uv run authsome daemon stop
rm -rf ~/.authsome
```
