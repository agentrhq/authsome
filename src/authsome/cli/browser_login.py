"""CloakBrowser-based login helper for browser_sso flows.

Imported lazily by the CLI login command only when auth_type == browser_sso.
Requires the optional 'browser' extra: pip install authsome[browser]
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger

CLOAKBROWSER_INSTALL_HINT = (
    "Browser SSO requires the optional browser extra.\n"
    "Install it with:  pip install 'authsome[browser]'\n"
    "Or directly:      pip install cloakbrowser"
)

_POLL_INTERVAL_S = 2.0
_DEFAULT_TIMEOUT_S = 300


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
) -> dict[str, str]:
    """Extract named credential values from a CloakBrowser persistent context.

    Uses the synchronous Playwright/CloakBrowser cookie API (context.cookies()).
    Only rules with `from == "cookies"` are handled; localStorage is not yet supported.
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

    return result


def _validate_credentials_sync(
    context: Any,
    credentials: dict[str, str],
    validate_url: str | None,
    extra_headers: dict[str, str],
) -> bool:
    """Check validate_url using a Playwright page.request. Returns True if 2xx."""
    if not validate_url:
        return bool(credentials)

    page = context.new_page()
    try:
        resp = page.request.get(
            validate_url,
            headers=extra_headers,
            timeout=8000,
        )
        return 200 <= resp.status < 300
    except Exception as exc:
        logger.debug("Browser SSO validation request failed: {}", exc)
        return False
    finally:
        page.close()


def _render_headers_sync(extra_headers: dict[str, str], credentials: dict[str, str]) -> dict[str, str]:
    """Render ${key} placeholder headers on the CLI side (mirrors service._render_extra_headers)."""
    import re
    _tmpl = re.compile(r"\$\{([\w-]+)\}")
    return {
        name: _tmpl.sub(lambda m: credentials.get(m.group(1), ""), template)
        for name, template in extra_headers.items()
    }


def run_browser_login(
    provider_name: str,
    action: dict[str, Any],
    *,
    timeout_s: float = _DEFAULT_TIMEOUT_S,
) -> dict[str, str]:
    """Open CloakBrowser, wait for user login, return extracted credentials.

    Runs synchronously (blocking). Call via asyncio.to_thread() from async code.

    Raises:
        ImportError: if cloakbrowser is not installed.
        RuntimeError: if login times out or credentials never validate.
    """
    try:
        from cloakbrowser import launch_persistent_context
    except ImportError as exc:
        raise ImportError(CLOAKBROWSER_INSTALL_HINT) from exc

    entry_url: str = action["entry_url"]
    domains: list[str] = action.get("domains", [])
    validate_url: str | None = action.get("validate_url")
    extract_rules: list[dict[str, Any]] = action.get("extract", [])
    extra_headers: dict[str, str] = action.get("extra_headers", {})
    network_proxy: str | None = action.get("network_proxy")
    login_mode: str = action.get("login_mode", "auto")

    profile_dir = Path.home() / ".authsome" / "browser-profiles" / provider_name
    profile_dir.mkdir(parents=True, exist_ok=True)

    headless = login_mode == "headless"

    launch_kwargs: dict[str, Any] = {
        "user_data_dir": str(profile_dir),
        "headless": headless,
    }
    if network_proxy:
        launch_kwargs["proxy"] = {"server": network_proxy}

    context = launch_persistent_context(**launch_kwargs)
    try:
        page = context.new_page()
        page.goto(entry_url)

        import time
        deadline = time.monotonic() + timeout_s

        while time.monotonic() < deadline:
            time.sleep(_POLL_INTERVAL_S)
            credentials = extract_cookies_from_context(context, extract_rules, domains)
            if credentials:
                rendered_headers = _render_headers_sync(extra_headers, credentials)
                if _validate_credentials_sync(context, credentials, validate_url, rendered_headers):
                    logger.info("Browser SSO: credentials validated for {}", provider_name)
                    return credentials

        raise RuntimeError(
            f"Browser SSO login timed out after {int(timeout_s)}s for '{provider_name}'.\n"
            "Please complete login in the browser window before the timeout."
        )
    finally:
        context.close()
