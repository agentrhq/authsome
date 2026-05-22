# CLI Design Review — authsome 0.3.0

_Generated: 2026-05-17_
_Scope: audit of the CLI surface against (1) published docs, (2) implementation, (3) industry conventions (clig.dev, gh, stripe, fly, kubectl)._

---

## Summary

Three categories of issues:

1. **Docs vs. implementation gaps** — documented behavior that the code no longer matches.
2. **Implementation bugs** — the code is broken relative to stated intent.
3. **Design gaps vs. industry conventions** — opportunities to align with well-established patterns.

---

## 1. Docs vs. Implementation Gaps

### 1a. Exit code table is completely wrong

**`docs/site/reference/cli.mdx` says:**

| Code | Meaning |
|------|---------|
| 2 | Invalid usage |
| 3 | Provider not found |
| 4 | Authentication failed |
| 5 | Credential missing |
| 6 | Refresh failed |
| 7 | Store unavailable |
| 8 | User cancelled credential entry |

**`src/authsome/utils.py:format_error_code` actually does:**

| Code | Exception(s) |
|------|------|
| 1 | Generic / unrecognized |
| 2 | `AuthenticationFailedError`, `InputCancelledError` |
| 3 | `ConnectionNotFoundError` |
| 4 | `ProviderNotFoundError`, `OperationNotAllowedError` |
| 5 | `CredentialMissingError`, `TokenExpiredError`, `RefreshFailedError` |
| 6 | `ConnectionAlreadyExistsError` |
| 7 | `ProviderAlreadyRegisteredError`, `FileExistsError` |
| 8 | `EndpointUnreachableError` |
| 9 | `DaemonUnavailableError` |

Every code from 2 onwards maps to a different error than documented. Scripts checking exit codes against the published table will behave incorrectly. The table in the docs needs a full replacement.

---

### 1b. `set-default` is a top-level command, not `connection set-default`

Docs say: `uvx authsome connection set-default <provider> <connection>`  
CLI binary exposes: `authsome set-default <provider> <connection>` at the root

The `connection` namespace documented does not exist. Running `authsome connection set-default` raises an error.

---

### 1c. `doctor` check names have changed

Docs and manual-testing guide mention checks named `config`, `providers`, `vault`.  
Current implementation returns: `spec_version`, `identity`, `providers`, `connections`, `vault`, `integrity`.  
`config` is gone. Three new checks are present and undocumented.

---

### 1d. `--log-file` default path is wrong in docs

Docs say default: `~/.authsome/logs/authsome.log`.  
`--help` output shows: `~/.authsome/client/logs/authsome.log`.

---

### 1e. `profile` command exists but is not documented

`authsome advanced profile` with subcommands `create` and `use` appears in the CLI but is absent from `docs/site/reference/cli.mdx`.

---

### 1f. `export` has a `shell` format not documented

`authsome export --format` accepts `env`, `json`, and `shell`.  
The CLI reference documents only `env` and `json`.

---

### 1g. `daemon logs` subcommand — docs show `-n 100`, actual flag is different

Docs say `authsome advanced daemon logs [-n 100]`. Actual `authsome advanced log` (client log command) uses `-n / --lines COUNT`.  
These are two different commands (`daemon logs` tails the daemon log; `log` tails the client audit log) — the distinction and both flags need clear documentation.

---

## 2. Implementation Bugs

### 2a. `doctor` renders `spec_version` as FAIL on every healthy system

**Location:** `src/authsome/cli/main.py:930`, `src/authsome/server/routes/health.py:32`

The server stores the spec version number as the value:
```python
checks["spec_version"] = str(current_spec_version())  # → "3"
```

The CLI checks `val == "ok"` for every key, so `"3" != "ok"` always renders `FAIL` even on a healthy install.

**Fix (server side):** Return `"ok"` for a passing check; surface the version number in a separate key (e.g., `spec_version_number: "3"`).  
**Fix (CLI side):** Treat `spec_version` as a special case that passes when the value is a numeric string.

---

### 2b. `--force` on `register` does not skip the confirmation prompt

**Location:** `src/authsome/cli/main.py:698–733`

The confirmation prompt checks only `yes` flag, not `force`. Running `authsome advanced register --force` still prompts interactively; piping no input causes a generic failure (exit 1, no useful message).

The `--force` flag is forwarded only to the server for the duplicate-override check. The client prompt is never bypassed.

**Current state:** `--force` and `--yes` have different, non-overlapping effects. A full "force overwrite silently" requires `--force --yes`.  
**Fix:** Either document the split explicitly in both `--help` and docs, or make `--force` imply `--yes` (the more ergonomic convention — `docker rm -f` and `git push --force` do not prompt).

---

### 2c. `--quiet` silences ALL output, including primary data

**Location:** `src/authsome/cli/context.py:52–54`

`echo()` returns immediately when `quiet=True`. This means `authsome --quiet list` produces zero output — the provider table is suppressed alongside any informational banners.

**Industry convention (clig.dev, gh):** `--quiet` suppresses status messages, progress indicators, and banners. It does NOT suppress the primary result (data rows, IDs, URLs). Errors always print to stderr regardless of `--quiet`.

**Fix:** Split `echo()` into a data path (`emit()`) and an info path (`note()`). Apply `quiet` suppression only to `note()`.

---

### 2d. `daemon stop` reports stopped but daemon immediately restarts

`authsome advanced daemon stop` outputs "Daemon stopped." and exits 0, but a subsequent `authsome advanced daemon status` shows `running: true` within milliseconds. The guide test for `running: false` after stop cannot pass.

Whether this is supervision auto-restart or a race in the status check is not confirmed, but the CLI output creates a misleading state. Either the daemon should indicate it will restart, or the stop command should wait for the process to actually stop before returning.

---

## 3. Design Gaps vs. Industry Conventions

### 3a. `inspect` and `get` serve overlapping purposes

Current situation:
- `authsome get <provider>` — returns connection metadata; secrets redacted; accepts `--field`, `--show-secret`, `--json`
- `authsome inspect <provider>` — returns full provider definition + connection summary as JSON (always)

This creates confusion: users must know that `get` is for connection state and `inspect` is for provider config. The `--json` flag on `inspect` is redundant because `inspect` always outputs JSON.

**Convention (kubectl, docker, gh):**
- `describe` / `inspect` — human-readable detail combining metadata and context
- `get` — scriptable, machine-readable fetch

**Recommendation:** Make `inspect` human-readable (like `kubectl describe`) and `get` the JSON-native scriptable path. Or merge into a single `show <provider>` command that defaults to human-readable and accepts `--json`. Either way, the two commands should not both exist at the same conceptual level without a clear, documented distinction.

---

### 3b. `--force` and `--yes` semantics need to follow convention

Industry standard (clig.dev, `gh`, `fly`):
- `--yes` / `-y`: skip interactive confirmation prompts
- `--force` / `-f`: override a safety constraint the tool would otherwise refuse

Currently, `register --force` means "server-side overwrite" and `register --yes` means "skip client prompt" — this is a valid split, but it's not what most users expect when they reach for `--force`. The `--help` text for `--force` says "Force overwrite if provider exists" which implies the prompt is also skipped.

**Recommendation:** `--force` should imply `--yes` (skips the prompt AND forces the overwrite). If the server-side distinction must be preserved, document it explicitly or rename the server-side flag to `--overwrite` internally.

---

### 3c. `set-default` should be under a command group

`authsome set-default <provider> <connection>` at the top level is an outlier. It's a CRUD operation on a connection property, and the docs already (correctly) document it as `connection set-default`.

**Convention (gh, kubectl, fly):** CRUD on a sub-resource belongs under a noun group. `kubectl label node`, `gh repo set-default`, `fly machine update` all group the resource type first.

**Recommendation:** Implement `authsome connection set-default` as documented (or `authsome connection default <provider> <connection>` for a simpler form). Remove or alias the flat `set-default`.

---

### 3d. Exit code range is too wide

The current scheme uses codes 1–9. `sysexits.h` reserves 64–78 for application errors; POSIX reserves 126–128+ for shell-level errors. Codes 1–9 are in the safe application range, but:

- Code 2 is used for `AuthenticationFailedError` — but shells and Click both use 2 for "usage error / bad arguments". This clash means a usage error and an authentication failure are indistinguishable.
- `gh` uses only 0, 1, 2, 4 and documents them clearly.

**Recommendation:** Reserve 2 strictly for argument/usage errors (Click's default). Shift application errors to 3–9 (or adopt `sysexits.h` 64+ for a cleaner split). Update the docs table to match.

---

### 3e. `--json` is redundant on `inspect` and missing on `daemon status`

- `inspect` always outputs JSON regardless of `--json` flag. The flag is a no-op but appears in `--help`, misleading users.
- `daemon status` always outputs JSON. There is no human-readable plain-text mode for `daemon status`.

**Recommendation:** 
- `inspect` should have a human-readable default and use `--json` to switch to machine output (like every other command).
- `daemon status` should follow the same pattern — plain text summary by default, `--json` for structured output.

---

### 3f. `remove` help text doesn't mention bundled providers

`authsome advanced remove --help` says "Permanently uninstall the specified custom PROVIDER definition."  
The CLI reference says `remove` also "resets to bundled" when used on a bundled provider.

If the behavior differs for bundled vs. custom providers, the `--help` text should say so. Users who accidentally run `authsome advanced remove github` should know whether they're deleting something permanently or just resetting to defaults.

---

## Recommended Priority Order

| Priority | Item | Effort |
|----------|------|--------|
| P0 | Fix `doctor` `spec_version: FAIL` rendering bug | Small |
| P0 | Fix exit code documentation table | Small |
| P1 | Fix `--quiet` — stop suppressing data output | Medium |
| P1 | Fix `--force` on `register` — imply `--yes` or document split | Small |
| P1 | Add `connection set-default` subgroup (or alias to match docs) | Small |
| P1 | Document `profile` command, `shell` export format, corrected `--log-file` path | Small |
| P2 | Resolve `inspect` vs `get` overlap — pick a clear model | Medium |
| P2 | Add human-readable default to `inspect` and `daemon status` | Medium |
| P2 | Fix `daemon stop` — wait for actual stop before returning | Medium |
| P2 | Fix exit code 2 clash with Click usage errors | Small |
| P3 | Update manual-testing.md to match current check names and exit codes | Small |

---

## Correct Exit Code Table (matches `format_error_code` as-is)

Replace the table in `docs/site/reference/cli.mdx`:

| Code | Meaning | Error class |
|------|---------|-------------|
| 0 | Success | — |
| 1 | Unexpected failure | Unclassified exceptions |
| 2 | Authentication failed or input cancelled | `AuthenticationFailedError`, `InputCancelledError` |
| 3 | Connection not found | `ConnectionNotFoundError` |
| 4 | Provider not found or operation not allowed | `ProviderNotFoundError`, `OperationNotAllowedError` |
| 5 | Credential missing or token expired | `CredentialMissingError`, `TokenExpiredError`, `RefreshFailedError` |
| 6 | Connection already exists | `ConnectionAlreadyExistsError` |
| 7 | Provider already registered | `ProviderAlreadyRegisteredError` |
| 8 | Endpoint unreachable | `EndpointUnreachableError` |
| 9 | Daemon unavailable | `DaemonUnavailableError` |

Note: Click argument validation errors (missing required argument, unknown option) produce exit code 2 via Click's own mechanism — this overlaps with `AuthenticationFailedError`. Consider shifting application codes up by one (3 → authentication, 4 → connection not found, …) to cleanly reserve 2 for usage errors.
