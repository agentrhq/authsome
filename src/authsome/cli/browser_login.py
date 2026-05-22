"""Browser-based login helper for browser_sso flows.

Uses the system Chrome/Chromium via Playwright.

Full sigcli-style three-step strategy:

  Step 0 — tryLiveSession
    Connect to an already-running Chrome via CDP (``--remote-debugging-port``).
    Reads cookies from your live browser session without launching anything new.
    Requires Chrome to have been started with a debug port (see below).

  Step 1 — tryExistingCookies
    Headless launch against the real Chrome profile — no window, no navigation.
    Works when Chrome is fully closed.  Finds existing login instantly.
    Falls back to the authsome shared profile if the real profile is locked.

  Step 2 — tryVisible
    Opens a full browser window, navigates to entry_url, polls until the user
    finishes logging in.  Uses the first unlocked profile dir.

────────────────────────────────────────────────────────────────────────────
Enable CDP (step 0) by launching Chrome with a remote-debug port:

  macOS:
    /Applications/Google\\ Chrome.app/Contents/MacOS/Google\\ Chrome \\
        --remote-debugging-port=9222 &

  Linux:
    google-chrome --remote-debugging-port=9222 &

  Or add it to your Chrome shortcut / .desktop launcher permanently so
  authsome can always read your live session without opening any window.
────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import platform
import time
from pathlib import Path
from typing import Any

from loguru import logger

PLAYWRIGHT_INSTALL_HINT = (
    "Browser SSO requires playwright.\n"
    "Install it with:  pip install playwright\n"
    "  (no 'playwright install' needed — authsome uses your system Chrome)"
)

# Fallback profile when the real Chrome profile is locked (Chrome already open).
AUTHSOME_BROWSER_DATA_DIR = Path.home() / ".authsome" / "browser-data"

# Alias kept for backwards-compat with any code that imported the old name.
SHARED_BROWSER_DATA_DIR = AUTHSOME_BROWSER_DATA_DIR

_POLL_INTERVAL_S = 4.0
_DEFAULT_TIMEOUT_S = 300

# Ports probed when looking for a running Chrome with --remote-debugging-port.
_CDP_PORTS = [9222, 9223, 9224, 9229]

# Flags that remove Playwright's automation fingerprint so Google OAuth and
# other sites do not block the session as a bot.
_STEALTH_ARGS = ["--disable-blink-features=AutomationControlled"]
_STEALTH_IGNORE = ["--enable-automation"]


# ---------------------------------------------------------------------------
# Browser / profile auto-detection
# ---------------------------------------------------------------------------


def _find_chrome_exec() -> str | None:
    """Return a path to the first Chrome/Chromium-compatible binary found."""
    system = platform.system()

    if system == "Darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
    elif system == "Linux":
        candidates = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
        ]
    elif system == "Windows":
        import os

        candidates = [
            os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%PROGRAMFILES%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        ]
    else:
        candidates = []

    for path in candidates:
        if Path(path).exists():
            logger.debug("authsome: found browser at {}", path)
            return path
    return None


def _find_real_chrome_data_dir() -> Path | None:
    """Return the user's real Chrome data directory if it exists on disk.

    When Chrome is closed, Playwright can launch against it headlessly and
    find existing session cookies — meaning authsome login requires no visible
    window at all (step 1).  When Chrome is open and has a debug port,
    step 0 attaches directly without needing the data dir at all.
    """
    system = platform.system()
    home = Path.home()

    if system == "Darwin":
        candidates = [
            home / "Library/Application Support/Google/Chrome",
            home / "Library/Application Support/BraveSoftware/Brave-Browser",
            home / "Library/Application Support/Chromium",
        ]
    elif system == "Linux":
        candidates = [
            home / ".config/google-chrome",
            home / ".config/BraveSoftware/Brave-Browser",
            home / ".config/chromium",
        ]
    elif system == "Windows":
        import os

        local = Path(os.environ.get("LOCALAPPDATA", ""))
        candidates = [
            local / "Google/Chrome/User Data",
            local / "BraveSoftware/Brave-Browser/User Data",
        ]
    else:
        candidates = []

    for p in candidates:
        if p.exists():
            logger.debug("authsome: found real Chrome profile at {}", p)
            return p
    return None


def _candidate_data_dirs(override: str | None = None) -> list[Path]:
    """Return profile directories to try, in priority order.

    1. Explicit ``browser_data_dir`` override from the provider config.
    2. User's real Chrome profile (requires Chrome to be closed).
    3. authsome shared fallback at ``~/.authsome/browser-data/``.
    """
    if override:
        return [Path(override).expanduser()]

    dirs: list[Path] = []
    real = _find_real_chrome_data_dir()
    if real:
        dirs.append(real)
    dirs.append(AUTHSOME_BROWSER_DATA_DIR)
    return dirs


# ---------------------------------------------------------------------------
# Cookie extraction helpers
# ---------------------------------------------------------------------------


def _is_domain_match(cookie_domain: str, domains: list[str]) -> bool:
    """Return True if cookie_domain belongs to any of the configured domains."""
    normalized = cookie_domain.lstrip(".")
    for d in domains:
        nd = d.lstrip(".")
        if normalized == nd or normalized.endswith("." + nd):
            return True
    return False


def extract_cookies_from_context(
    context: Any,
    extract_rules: list[dict[str, Any]],
    domains: list[str],
    ttl_from_cookie: str | None = None,
) -> dict[str, str]:
    """Extract named credential values from a Playwright BrowserContext.

    Works for both ``launch_persistent_context`` contexts and CDP-attached
    contexts returned by ``connect_over_cdp``.

    If ``ttl_from_cookie`` is set, the Unix ``expires`` timestamp of that
    cookie is stored under the reserved key ``"__cookie_expires_at__"``.
    The daemon uses this real expiry instead of relying on an estimated ttl.
    """
    all_cookies = context.cookies()
    domain_cookies = [c for c in all_cookies if _is_domain_match(c.get("domain", ""), domains)]

    result: dict[str, str] = {}
    for rule in extract_rules:
        if rule.get("from") != "cookies":
            continue
        name = rule["as"]
        match = rule.get("match", "*")

        if match == "*":
            result[name] = "; ".join(f"{c['name']}={c['value']}" for c in domain_cookies)
        else:
            for c in domain_cookies:
                if c["name"] == match:
                    result[name] = c["value"]
                    break

    # Capture the real server-set expiry from the designated primary cookie.
    # Playwright returns expires as a Unix float; -1 means a session cookie.
    if ttl_from_cookie:
        for c in domain_cookies:
            if c["name"] == ttl_from_cookie:
                expires_ts = c.get("expires", -1)
                if isinstance(expires_ts, int | float) and expires_ts > 0:
                    result["__cookie_expires_at__"] = str(int(expires_ts))
                break

    return result


def _credentials_ready_for_validation(
    credentials: dict[str, str],
    extract_rules: list[dict[str, Any]],
) -> bool:
    """Return True only when named cookies (not just guest cookies) are present.

    Wildcard rules (``match="*"``) are skipped because they get populated early
    with guest-only cookies before the user logs in.  Every named rule
    (e.g. ``auth_token``, ``ct0``) must be present before we call validate_url.
    """
    required_keys: list[str] = []
    for rule in extract_rules:
        if rule.get("from") != "cookies":
            continue
        if rule.get("match", "*") == "*":
            continue
        required_keys.append(rule["as"])

    if not required_keys:
        cookie_blob = credentials.get("cookie", "")
        return bool(cookie_blob and "=" in cookie_blob)

    return all(credentials.get(key) for key in required_keys)


def _render_headers_sync(extra_headers: dict[str, str], credentials: dict[str, str]) -> dict[str, str]:
    """Render ``${key}`` placeholders in extra_headers using extracted credentials."""
    import re

    _tmpl = re.compile(r"\$\{([\w-]+)\}")
    return {
        name: _tmpl.sub(lambda m: credentials.get(m.group(1), ""), template) for name, template in extra_headers.items()
    }


def _validate_credentials_sync(
    context: Any,
    credentials: dict[str, str],
    validate_url: str | None,
    extra_headers: dict[str, str],
) -> bool:
    """Check validate_url via APIRequestContext — no new browser tabs opened."""
    if not validate_url:
        return bool(credentials)

    try:
        resp = context.request.get(
            validate_url,
            headers=extra_headers,
            timeout=8000,
        )
        return 200 <= resp.status < 300
    except Exception as exc:
        logger.debug("Browser SSO validation request failed: {}", exc)
        return False


# ---------------------------------------------------------------------------
# Step 0 — tryLiveSession (CDP attach to running Chrome)
# ---------------------------------------------------------------------------


def _try_live_cdp_session(
    provider_name: str,
    extract_rules: list[dict[str, Any]],
    domains: list[str],
    ttl_from_cookie: str | None,
    validate_url: str | None,
    extra_headers: dict[str, str],
) -> dict[str, str] | None:
    """Attach to an already-running Chrome via CDP and read its live cookies.

    Chrome must have been started with ``--remote-debugging-port=<port>``.
    Probes ``_CDP_PORTS`` in order; skips silently if none respond.

    This is the truest sigcli-style step: zero launches, zero windows,
    cookies come directly from the user's live browsing session.
    ``browser.close()`` on a CDP connection only *disconnects* — it does NOT
    close the user's Chrome.
    """
    from playwright.sync_api import sync_playwright

    for port in _CDP_PORTS:
        try:
            with sync_playwright() as p:
                browser = p.chromium.connect_over_cdp(
                    f"http://localhost:{port}",
                    timeout=2000,
                )
                try:
                    for context in browser.contexts:
                        credentials = extract_cookies_from_context(context, extract_rules, domains, ttl_from_cookie)
                        if not _credentials_ready_for_validation(credentials, extract_rules):
                            continue
                        rendered = _render_headers_sync(extra_headers, credentials)
                        if _validate_credentials_sync(context, credentials, validate_url, rendered):
                            logger.info(
                                "authsome: live Chrome session on :{} has valid cookies for {} — no window needed",
                                port,
                                provider_name,
                            )
                            return credentials
                finally:
                    browser.close()  # disconnects only, does NOT close Chrome
        except Exception as exc:
            logger.debug("CDP :{} not available: {}", port, exc)

    return None


# ---------------------------------------------------------------------------
# Step 1 — tryExistingCookies (headless launch, no navigation, no window)
# ---------------------------------------------------------------------------


def _try_existing_cookies_in_dir(
    data_dir: Path,
    extract_rules: list[dict[str, Any]],
    domains: list[str],
    ttl_from_cookie: str | None,
    validate_url: str | None,
    extra_headers: dict[str, str],
    chrome_exec: str | None,
) -> dict[str, str] | None:
    """Try one specific data_dir headlessly. Returns credentials or None."""
    from playwright.sync_api import sync_playwright

    data_dir.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as p:
            launch_kwargs: dict[str, Any] = {
                "user_data_dir": str(data_dir),
                "headless": True,
                "args": _STEALTH_ARGS,
                "ignore_default_args": _STEALTH_IGNORE,
            }
            if chrome_exec:
                launch_kwargs["executable_path"] = chrome_exec

            context = p.chromium.launch_persistent_context(**launch_kwargs)
            try:
                credentials = extract_cookies_from_context(context, extract_rules, domains, ttl_from_cookie)
                if not _credentials_ready_for_validation(credentials, extract_rules):
                    return None
                rendered = _render_headers_sync(extra_headers, credentials)
                if _validate_credentials_sync(context, credentials, validate_url, rendered):
                    return credentials
                return None
            finally:
                context.close()
    except Exception as exc:
        # Profile locked (Chrome already open) or other launch error — tolerated.
        logger.debug("tryExistingCookies skipped for {}: {}", data_dir, exc)
        return None


def _try_existing_cookies(
    provider_name: str,
    extract_rules: list[dict[str, Any]],
    domains: list[str],
    ttl_from_cookie: str | None,
    validate_url: str | None,
    extra_headers: dict[str, str],
    chrome_exec: str | None,
    data_dirs: list[Path],
) -> dict[str, str] | None:
    """Try each data dir in order; return the first valid credentials found."""
    for data_dir in data_dirs:
        result = _try_existing_cookies_in_dir(
            data_dir,
            extract_rules,
            domains,
            ttl_from_cookie,
            validate_url,
            extra_headers,
            chrome_exec,
        )
        if result is not None:
            logger.info(
                "authsome: existing cookies valid for {} (profile: {}) — no window needed",
                provider_name,
                data_dir,
            )
            return result
    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def run_browser_login(
    provider_name: str,
    action: dict[str, Any],
    *,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
) -> dict[str, str]:
    """Authenticate via browser and return extracted credentials.

    Full sigcli-style three-step strategy:

    0. **tryLiveSession** — attach to a running Chrome via CDP.  Requires
       Chrome to be open with ``--remote-debugging-port=9222`` (or similar).
       Zero launches, zero windows — reads cookies from your live session.

    1. **tryExistingCookies** — headless launch against real Chrome profile.
       Requires Chrome to be *closed*.  Finds existing login instantly with
       no visible window.  Falls back to authsome's own profile if locked.

    2. **tryVisible** — opens a full browser window, navigates to
       ``entry_url``, polls until credentials pass ``validate_url``.

    Runs synchronously (blocking).  Call via ``asyncio.to_thread()`` from async.

    Raises
    ------
    ImportError
        If ``playwright`` is not installed.
    RuntimeError
        If the user does not complete login within ``timeout_s`` seconds.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ImportError(PLAYWRIGHT_INSTALL_HINT) from exc

    entry_url: str = action["entry_url"]
    domains: list[str] = action.get("domains", [])
    validate_url: str | None = action.get("validate_url")
    extract_rules: list[dict[str, Any]] = action.get("extract", [])
    extra_headers: dict[str, str] = action.get("extra_headers", {})
    network_proxy: str | None = action.get("network_proxy")
    login_mode: str = action.get("login_mode", "auto")
    ttl_from_cookie: str | None = action.get("ttl_from_cookie")
    chrome_exec: str | None = action.get("browser_exec") or _find_chrome_exec()
    data_dirs = _candidate_data_dirs(action.get("browser_data_dir"))

    if login_mode == "auto":
        # ------------------------------------------------------------------
        # Step 0: tryLiveSession — attach to running Chrome via CDP
        # ------------------------------------------------------------------
        live = _try_live_cdp_session(
            provider_name,
            extract_rules,
            domains,
            ttl_from_cookie,
            validate_url,
            extra_headers,
        )
        if live:
            return live

        # ------------------------------------------------------------------
        # Step 1: tryExistingCookies — headless launch, no window
        # ------------------------------------------------------------------
        existing = _try_existing_cookies(
            provider_name,
            extract_rules,
            domains,
            ttl_from_cookie,
            validate_url,
            extra_headers,
            chrome_exec,
            data_dirs,
        )
        if existing:
            return existing

    # ------------------------------------------------------------------
    # Step 2: tryVisible (or headless if login_mode == "headless")
    # Determine which profile dir Chrome is not currently holding open.
    # ------------------------------------------------------------------
    headless = login_mode == "headless"
    active_data_dir: Path = data_dirs[-1]  # safest fallback = authsome dir

    for candidate in data_dirs:
        candidate.mkdir(parents=True, exist_ok=True)
        try:
            with sync_playwright() as p:
                probe_kwargs: dict[str, Any] = {
                    "user_data_dir": str(candidate),
                    "headless": True,
                    "args": _STEALTH_ARGS,
                    "ignore_default_args": _STEALTH_IGNORE,
                }
                if chrome_exec:
                    probe_kwargs["executable_path"] = chrome_exec
                ctx = p.chromium.launch_persistent_context(**probe_kwargs)
                ctx.close()
            active_data_dir = candidate
            break
        except Exception:
            logger.debug("Profile {} is locked, trying next candidate", candidate)

    label = "real Chrome profile" if active_data_dir != AUTHSOME_BROWSER_DATA_DIR else "authsome profile"
    logger.info("authsome: opening browser ({}) for {}", label, provider_name)

    launch_kwargs: dict[str, Any] = {
        "user_data_dir": str(active_data_dir),
        "headless": headless,
        "args": _STEALTH_ARGS,
        "ignore_default_args": _STEALTH_IGNORE,
    }
    if chrome_exec:
        launch_kwargs["executable_path"] = chrome_exec
    if network_proxy:
        launch_kwargs["proxy"] = {"server": network_proxy}

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(**launch_kwargs)
        try:
            page = context.new_page()
            page.goto(entry_url)

            deadline = time.monotonic() + timeout_s
            while time.monotonic() < deadline:
                time.sleep(_POLL_INTERVAL_S)
                credentials = extract_cookies_from_context(context, extract_rules, domains, ttl_from_cookie)
                if not _credentials_ready_for_validation(credentials, extract_rules):
                    continue
                rendered = _render_headers_sync(extra_headers, credentials)
                if _validate_credentials_sync(context, credentials, validate_url, rendered):
                    logger.info("authsome: browser SSO credentials validated for {}", provider_name)
                    return credentials

        finally:
            context.close()

    raise RuntimeError(
        f"Browser SSO login timed out after {int(timeout_s)}s for '{provider_name}'.\n"
        "Please complete login in the browser window before the timeout."
    )
