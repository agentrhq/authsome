"""Browser-based login helper for browser auth flows.

Uses the system Chrome binary via Playwright against a **dedicated authsome
profile** at ``~/.authsome/browser-data/`` — the same model as sigcli's
``~/.sig/browser-data``.  We never touch the user's daily Chrome profile unless
``browser_data_dir`` is explicitly set in the provider config.

sigcli-style cascade (``login_mode=auto``):

  1. tryExistingCookies — headless, ``about:blank``, read stored cookies.
                          Instant success when a previous login is still valid.
  2. tryVisible         — open a real browser window for interactive login.

Headless navigation (``login_mode=headless``) is available but many sites
(including LinkedIn) block or break in headless mode — prefer ``auto`` or
``visible`` for first-time login.

Optional fast-path: if Chrome is already running with ``--remote-debugging-port``,
we attach via CDP and read cookies without launching anything.
"""

from __future__ import annotations

import platform
import time
from pathlib import Path
from typing import Any, TypedDict

from loguru import logger

from authsome.auth.browser_cookies import normalize_browser_credentials

PLAYWRIGHT_INSTALL_HINT = (
    "Browser requires playwright.\n"
    "Install it with:  pip install playwright\n"
    "  (no 'playwright install' needed — authsome uses your system Chrome)"
)

CHROME_NOT_FOUND_HINT = "Chrome not found. Install Google Chrome (or Chromium/Brave), "

# Dedicated authsome browser profile — shared across all browser providers.
AUTHSOME_BROWSER_DATA_DIR = Path.home() / ".authsome" / "browser-data"

# Alias kept for backwards-compat with any code that imported the old name.
SHARED_BROWSER_DATA_DIR = AUTHSOME_BROWSER_DATA_DIR

_POLL_INTERVAL_S = 4.0
_DEFAULT_TIMEOUT_S = 300
_HEADLESS_TIMEOUT_S = 20.0
_LOGIN_PAGE_SETTLE_S = 5.0

# Optional fast-path: attach to a Chrome already running with a debug port.
_CDP_PORTS = [9222, 9223, 9224, 9229]

_LOGIN_URL_PATTERNS = (
    "/login",
    "/signin",
    "/sign-in",
    "/auth",
    "/checkpoint",
    "/uas/login",
)

_CHROME_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
]
_CHROME_IGNORE_DEFAULT_ARGS = ["--enable-automation"]


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


def _require_chrome_exec(chrome_exec: str | None) -> None:
    if not chrome_exec:
        raise RuntimeError(CHROME_NOT_FOUND_HINT)


def _browser_data_dir(override: str | None = None) -> Path:
    """Return the browser profile directory authsome should use."""
    if override:
        return Path(override).expanduser()
    return AUTHSOME_BROWSER_DATA_DIR


def _build_launch_kwargs(
    data_dir: Path,
    *,
    headless: bool,
    chrome_exec: str | None,
    network_proxy: str | None = None,
) -> dict[str, Any]:
    data_dir.mkdir(parents=True, exist_ok=True)
    kwargs: dict[str, Any] = {
        "user_data_dir": str(data_dir),
        "headless": headless,
        "args": _CHROME_ARGS,
        "ignore_default_args": _CHROME_IGNORE_DEFAULT_ARGS,
    }
    if chrome_exec:
        kwargs["executable_path"] = chrome_exec
    if network_proxy:
        kwargs["proxy"] = {"server": network_proxy}
    return kwargs


def _is_login_url(url: str) -> bool:
    lower = url.lower()
    return any(p in lower for p in _LOGIN_URL_PATTERNS)


class _BrowserPollKwargs(TypedDict):
    extract_rules: list[dict[str, Any]]
    domains: list[str]
    ttl_from_cookie: str | None
    validate_url: str | None
    extra_headers: dict[str, str]
    chrome_exec: str | None
    network_proxy: str | None


# ---------------------------------------------------------------------------
# Cookie extraction helpers
# ---------------------------------------------------------------------------


def _format_cookie_pair(name: str, value: str) -> str:
    """Format one cookie for the ``Cookie`` request header."""
    bare = value.strip().strip('"')
    if name == "JSESSIONID":
        return f'{name}="{bare}"'
    return f"{name}={value}"


def _derive_jsessionid(credentials: dict[str, str]) -> None:
    """Fill ``jsessionid`` from the cookie blob when the named cookie is missing."""
    normalized = normalize_browser_credentials(credentials)
    credentials.clear()
    credentials.update(normalized)


def _normalize_extracted_credentials(credentials: dict[str, str]) -> dict[str, str]:
    """Post-extraction normalizations for site-specific cookie quirks."""
    return normalize_browser_credentials(credentials)


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
    cookie_urls: list[str] | None = None,
) -> dict[str, str]:
    """Extract named credential values from a Playwright BrowserContext.

    Works for both ``launch_persistent_context`` contexts and CDP-attached
    contexts returned by ``connect_over_cdp``.

    If ``ttl_from_cookie`` is set, the Unix ``expires`` timestamp of that
    cookie is stored under the reserved key ``"__cookie_expires_at__"``.
    The daemon uses this real expiry instead of relying on an estimated ttl.
    """
    all_cookies = context.cookies(cookie_urls) if cookie_urls else context.cookies()
    domain_cookies = [c for c in all_cookies if _is_domain_match(c.get("domain", ""), domains)]

    result: dict[str, str] = {}
    for rule in extract_rules:
        if rule.get("from") != "cookies":
            continue
        name = rule["as"]
        match = rule.get("match", "*")

        if match == "*":
            result[name] = "; ".join(_format_cookie_pair(c["name"], c["value"]) for c in domain_cookies)
        else:
            for c in domain_cookies:
                if c["name"] == match:
                    result[name] = c["value"]
                    break

    result = _normalize_extracted_credentials(result)

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
    page: Any | None = None,
) -> bool:
    """Check validate_url without opening new browser tabs."""
    if not validate_url:
        return bool(credentials)

    try:
        # Prefer the active page's request context — same TLS/fingerprint as the login session.
        if page is not None:
            resp = page.request.get(validate_url, headers=extra_headers, timeout=8000)
            status = resp.status
        else:
            import httpx

            resp = httpx.get(
                validate_url,
                headers=extra_headers,
                timeout=8.0,
                follow_redirects=False,
            )
            status = resp.status_code

        if not (200 <= status < 300):
            logger.debug(
                "Browser validation returned status {} for {}",
                status,
                validate_url,
            )
        return 200 <= status < 300
    except Exception as exc:
        logger.debug("Browser validation request failed: {}", exc)
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
# Step 1 — tryExistingCookies (headless, about:blank, no window)
# ---------------------------------------------------------------------------


def _try_existing_cookies(
    provider_name: str,
    data_dir: Path,
    extract_rules: list[dict[str, Any]],
    domains: list[str],
    ttl_from_cookie: str | None,
    validate_url: str | None,
    extra_headers: dict[str, str],
    chrome_exec: str | None,
    network_proxy: str | None,
) -> dict[str, str] | None:
    """Headless read of stored cookies — no navigation beyond about:blank."""
    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                **_build_launch_kwargs(
                    data_dir,
                    headless=True,
                    chrome_exec=chrome_exec,
                    network_proxy=network_proxy,
                )
            )
            try:
                page = context.new_page()
                page.goto("about:blank")
                credentials = extract_cookies_from_context(
                    context,
                    extract_rules,
                    domains,
                    ttl_from_cookie,
                    _cookie_urls_for_domains(domains),
                )
                if not _credentials_ready_for_validation(credentials, extract_rules):
                    return None
                rendered = _render_headers_sync(extra_headers, credentials)
                if _validate_credentials_sync(context, credentials, validate_url, rendered):
                    logger.info(
                        "authsome: existing cookies valid for {} — no window needed",
                        provider_name,
                    )
                    return credentials
                return None
            finally:
                context.close()
    except Exception as exc:
        logger.debug("tryExistingCookies failed (tolerated): {}", exc)
        return None


# ---------------------------------------------------------------------------
# Step 2 — tryHeadless (headless, navigate, bail on login page)
# ---------------------------------------------------------------------------


def _cookie_urls_for_domains(domains: list[str]) -> list[str]:
    return [f"https://{d.lstrip('.')}" for d in domains]


def _poll_until_valid(
    context: Any,
    page: Any,
    extract_rules: list[dict[str, Any]],
    domains: list[str],
    ttl_from_cookie: str | None,
    validate_url: str | None,
    extra_headers: dict[str, str],
    *,
    deadline: float,
    exit_on_login_page: bool,
) -> dict[str, str] | None:
    """Poll cookies + validate_url until success, timeout, or login-page bail-out."""
    login_page_since: float | None = None
    cookie_urls = _cookie_urls_for_domains(domains)

    while time.monotonic() < deadline:
        credentials = extract_cookies_from_context(context, extract_rules, domains, ttl_from_cookie, cookie_urls)
        if _credentials_ready_for_validation(credentials, extract_rules):
            rendered = _render_headers_sync(extra_headers, credentials)
            if _validate_credentials_sync(context, credentials, validate_url, rendered, page=page):
                return credentials

        if exit_on_login_page:
            try:
                if _is_login_url(page.url):
                    if login_page_since is None:
                        login_page_since = time.monotonic()
                    elif time.monotonic() - login_page_since >= _LOGIN_PAGE_SETTLE_S:
                        logger.debug("Login page detected — switching to visible browser")
                        return None
                else:
                    login_page_since = None
            except Exception:
                pass

        time.sleep(_POLL_INTERVAL_S)

    return None


def _try_headless_login(
    provider_name: str,
    entry_url: str,
    data_dir: Path,
    extract_rules: list[dict[str, Any]],
    domains: list[str],
    ttl_from_cookie: str | None,
    validate_url: str | None,
    extra_headers: dict[str, str],
    chrome_exec: str | None,
    network_proxy: str | None,
) -> dict[str, str] | None:
    """Headless navigation — succeeds silently or yields to visible login."""
    from playwright.sync_api import sync_playwright

    logger.info("authsome: trying headless login for {}", provider_name)
    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                **_build_launch_kwargs(
                    data_dir,
                    headless=True,
                    chrome_exec=chrome_exec,
                    network_proxy=network_proxy,
                )
            )
            try:
                page = context.new_page()
                page.goto(entry_url)
                return _poll_until_valid(
                    context,
                    page,
                    extract_rules,
                    domains,
                    ttl_from_cookie,
                    validate_url,
                    extra_headers,
                    deadline=time.monotonic() + _HEADLESS_TIMEOUT_S,
                    exit_on_login_page=True,
                )
            finally:
                context.close()
    except Exception as exc:
        logger.debug("tryHeadless failed (tolerated): {}", exc)
        return None


# ---------------------------------------------------------------------------
# Step 3 — tryVisible (interactive login window)
# ---------------------------------------------------------------------------


def _try_visible_login(
    provider_name: str,
    entry_url: str,
    data_dir: Path,
    extract_rules: list[dict[str, Any]],
    domains: list[str],
    ttl_from_cookie: str | None,
    validate_url: str | None,
    extra_headers: dict[str, str],
    chrome_exec: str | None,
    network_proxy: str | None,
    timeout_s: float,
) -> dict[str, str] | None:
    """Open a visible browser window and wait for the user to finish logging in."""
    from playwright.sync_api import sync_playwright

    logger.info("authsome: opening visible browser for {}", provider_name)
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            **_build_launch_kwargs(
                data_dir,
                headless=False,
                chrome_exec=chrome_exec,
                network_proxy=network_proxy,
            )
        )
        try:
            page = context.new_page()
            page.goto(entry_url)
            return _poll_until_valid(
                context,
                page,
                extract_rules,
                domains,
                ttl_from_cookie,
                validate_url,
                extra_headers,
                deadline=time.monotonic() + timeout_s,
                exit_on_login_page=False,
            )
        finally:
            context.close()


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

    Runs synchronously (blocking).  Call via ``asyncio.to_thread()`` from async.

    Raises
    ------
    ImportError
        If ``playwright`` is not installed.
    RuntimeError
        If the user does not complete login within ``timeout_s`` seconds.
    """
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
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
    data_dir = _browser_data_dir(action.get("browser_data_dir"))

    poll_kwargs: _BrowserPollKwargs = {
        "extract_rules": extract_rules,
        "domains": domains,
        "ttl_from_cookie": ttl_from_cookie,
        "validate_url": validate_url,
        "extra_headers": extra_headers,
        "chrome_exec": chrome_exec,
        "network_proxy": network_proxy,
    }

    if login_mode == "visible":
        _require_chrome_exec(chrome_exec)
        result = _try_visible_login(provider_name, entry_url, data_dir, **poll_kwargs, timeout_s=timeout_s)
    elif login_mode == "headless":
        _require_chrome_exec(chrome_exec)
        result = _try_existing_cookies(provider_name, data_dir, **poll_kwargs)
        if result is None:
            result = _try_headless_login(provider_name, entry_url, data_dir, **poll_kwargs)
    else:
        # auto — full sigcli cascade
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

        _require_chrome_exec(chrome_exec)
        result = _try_existing_cookies(provider_name, data_dir, **poll_kwargs)
        if result is None:
            time.sleep(1.0)  # let any headless profile lock release before visible launch
            result = _try_visible_login(provider_name, entry_url, data_dir, **poll_kwargs, timeout_s=timeout_s)

    if result:
        logger.info("authsome: browser credentials validated for {}", provider_name)
        return result

    raise RuntimeError(
        f"Browser login timed out after {int(timeout_s)}s for '{provider_name}'.\n"
        "Please complete login in the browser window before the timeout."
    )
