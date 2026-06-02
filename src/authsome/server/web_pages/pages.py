"""HTML page generators for the Authsome server.

Design: Authsome Secure Console (see src/authsome/ui/DESIGN.md).
All pages follow the dark-first, developer-focused design system.
"""

from __future__ import annotations

import html
from typing import Any

from authsome.server.web_pages.web_theme import DARK_THEME_CSS, DEVICE_BRIDGE_STYLE

_BRAND = '<span class="brand-name">Authsome</span><span class="brand-dot">.</span>'


def _page_shell(title: str, head_extra: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(title)}</title>
    <style>{DARK_THEME_CSS}

      /* Brand */
      .brand-name {{ font-family: var(--font-mono); font-size: 13px; font-weight: 700;
                     letter-spacing: 0.04em; text-transform: uppercase; color: var(--muted-hi); }}
      .brand-dot  {{ color: var(--accent); }}

    </style>
    {head_extra}
  </head>
  <body>
    {body}
  </body>
</html>"""


def message_page(title: str, message: str) -> str:
    """Generate a simple message/error page."""
    body = f"""
    <main style="
      width: 100%; max-width: 440px; margin: 0 auto;
      padding: 32px 24px;
      display: flex; align-items: center; justify-content: center;
      min-height: 100vh;
    ">
      <div class="panel" style="width: 100%; padding: 28px;">
        <div style="margin-bottom: 20px;">{_BRAND}</div>
        <h1 style="font-size: 18px; font-weight: 600; letter-spacing: -0.01em;
                   margin-bottom: 10px;">{html.escape(title)}</h1>
        <p style="color: var(--muted); font-size: 14px; line-height: 1.6;">
          {html.escape(message)}
        </p>
      </div>
    </main>"""
    return _page_shell(f"Authsome — {title}", "", body)


def account_auth_page(
    *,
    next_url: str,
    active_tab: str = "login",
    identity: str | None = None,
    error: str | None = None,
) -> str:
    """Generate the account sign-in/register page."""
    page_title = "Claim identity" if identity else "Authsome Dashboard"
    subtitle = (
        f"Sign in to claim <strong style='color:var(--text);font-weight:500'>"
        f"{html.escape(identity)}</strong> to your account."
        if identity
        else "Sign in or create an account to open your dashboard."
    )

    error_block = ""
    if error:
        error_block = f"""
        <div style="
          margin-bottom: 16px; padding: 10px 14px;
          background: var(--error-bg); border: 1px solid var(--error-border);
          border-radius: var(--radius); color: var(--error); font-size: 13px;
        ">{html.escape(error)}</div>"""

    login_hidden = " hidden" if active_tab != "login" else ""
    register_hidden = " hidden" if active_tab != "register" else ""
    login_active = " tab-active" if active_tab == "login" else ""
    register_active = " tab-active" if active_tab == "register" else ""

    body = f"""
    <main style="
      width: 100%; max-width: 420px; margin: 0 auto;
      padding: 48px 20px 32px;
    ">
      <!-- Brand -->
      <div style="text-align: center; margin-bottom: 28px;">{_BRAND}</div>

      <!-- Auth Card -->
      <div class="panel">
        <!-- Header -->
        <div class="panel-header" style="text-align: center;">
          <h1 style="font-size: 20px; font-weight: 600; letter-spacing: -0.02em;
                     margin-bottom: 6px;">{html.escape(page_title)}</h1>
          <p style="color: var(--muted); font-size: 13px; line-height: 1.5; margin: 0;">
            {subtitle}
          </p>
        </div>

        <!-- Tab switcher -->
        <div style="
          display: grid; grid-template-columns: 1fr 1fr;
          gap: 6px; padding: 14px 20px; border-bottom: 1px solid var(--line);
        " role="tablist">
          <button class="tab-btn{login_active}" type="button"
            data-tab="login"
            role="tab" aria-selected="{"true" if active_tab == "login" else "false"}"
          >Sign in</button>
          <button class="tab-btn{register_active}" type="button"
            data-tab="register"
            role="tab" aria-selected="{"true" if active_tab == "register" else "false"}"
          >Create account</button>
        </div>

        <!-- Login panel -->
        <div id="panel-login" data-panel="login" class="panel-body"{login_hidden}>
          <p style="font-size: 13px; color: var(--muted); margin-bottom: 18px; line-height: 1.4;">
            Welcome back.
          </p>
          {error_block if active_tab == "login" else ""}
          <form method="post" action="/auth/login">
            <input type="hidden" name="next" value="{html.escape(next_url)}">
            <div class="field-group">
              <label for="login-email">Email</label>
              <input id="login-email" type="email" name="email"
                     placeholder="you@example.com" required autocomplete="email">
            </div>
            <div class="field-group" style="margin-bottom: 20px;">
              <label for="login-password">Password</label>
              <input id="login-password" type="password" name="password"
                     placeholder="••••••••" required autocomplete="current-password">
            </div>
            <button type="submit" class="btn btn-primary">Sign in</button>
          </form>
        </div>

        <!-- Register panel -->
        <div id="panel-register" data-panel="register" class="panel-body"{register_hidden}>
          <p style="font-size: 13px; color: var(--muted); margin-bottom: 18px; line-height: 1.4;">
            Get started in seconds — no billing information required.
          </p>
          {error_block if active_tab == "register" else ""}
          <form method="post" action="/auth/register">
            <input type="hidden" name="next" value="{html.escape(next_url)}">
            <div class="field-group">
              <label for="reg-email">Email</label>
              <input id="reg-email" type="email" name="email"
                     placeholder="you@example.com" required autocomplete="email">
            </div>
            <div class="field-group" style="margin-bottom: 20px;">
              <label for="reg-password">Password</label>
              <input id="reg-password" type="password" name="password"
                     placeholder="••••••••" required autocomplete="new-password">
            </div>
            <button type="submit" class="btn btn-primary">Create account</button>
          </form>
        </div>
      </div>

      <!-- Footer -->
      <p style="text-align: center; color: var(--muted); font-size: 12px;
                margin-top: 20px; line-height: 1.5;">
        Local credential manager &mdash; your data stays on this machine.
      </p>
    </main>

    <style>
      body {{ display: block; padding: 0; }}

      /* Tab buttons */
      .tab-btn {{
        font-family: var(--font-ui);
        font-size: 13px;
        font-weight: 500;
        padding: 8px 14px;
        border-radius: var(--radius);
        background: transparent;
        color: var(--muted);
        border: 1px solid var(--line);
        cursor: pointer;
        transition: color 0.15s, border-color 0.15s, background 0.15s;
        width: 100%;
      }}
      .tab-btn:hover {{
        color: var(--text);
        border-color: var(--line-accent);
        background: var(--accent-glow-sm);
      }}
      .tab-btn.tab-active {{
        color: var(--accent-dim);
        border-color: var(--accent);
        background: var(--accent-glow-sm);
        box-shadow: 0 0 0 1px var(--accent-glow);
      }}
      [hidden] {{ display: none !important; }}
    </style>

    <script>
      const tabs = document.querySelectorAll("[data-tab]");
      const panels = document.querySelectorAll("[data-panel]");

      function setTab(name) {{
        tabs.forEach(t => {{
          const active = t.dataset.tab === name;
          t.classList.toggle("tab-active", active);
          t.setAttribute("aria-selected", active ? "true" : "false");
        }});
        panels.forEach(p => {{
          p.hidden = p.dataset.panel !== name;
        }});
      }}

      tabs.forEach(t => t.addEventListener("click", () => setTab(t.dataset.tab)));
      setTab("{"register" if active_tab == "register" else "login"}");
    </script>"""

    return _page_shell(f"Authsome — {page_title}", "", body)


def account_claim_auth_page(*, token: str, identity: str, error: str | None = None, active_tab: str = "login") -> str:
    """Generate the account sign-in/register page for an identity claim."""
    return account_auth_page(
        next_url=f"/claim/{html.escape(token)}",
        active_tab=active_tab,
        identity=identity,
        error=error,
    )


def account_claim_confirm_page(*, token: str, identity: str, email: str) -> str:
    """Generate the identity-claim confirmation page."""
    body = f"""
    <main style="
      width: 100%; max-width: 420px; margin: 0 auto;
      padding: 48px 20px 32px;
    ">
      <div style="text-align: center; margin-bottom: 28px;">{_BRAND}</div>

      <div class="panel">
        <div class="panel-header" style="text-align: center;">
          <h1 style="font-size: 20px; font-weight: 600; letter-spacing: -0.02em;
                     margin-bottom: 6px;">Claim identity</h1>
          <p style="color: var(--muted); font-size: 13px; line-height: 1.5; margin: 0;">
            Review and confirm before linking.
          </p>
        </div>

        <div class="panel-body">
          <!-- Identity row -->
          <div style="
            background: var(--surface-dim); border: 1px solid var(--line);
            border-radius: var(--radius); padding: 12px 14px; margin-bottom: 16px;
          ">
            <div style="font-family: var(--font-mono); font-size: 11px; font-weight: 700;
                        text-transform: uppercase; letter-spacing: 0.08em;
                        color: var(--muted); margin-bottom: 6px;">Identity</div>
            <div style="font-family: var(--font-mono); font-size: 13px;
                        color: var(--accent-dim); word-break: break-all;">
              {html.escape(identity)}
            </div>
          </div>

          <!-- Account row -->
          <div style="
            background: var(--surface-dim); border: 1px solid var(--line);
            border-radius: var(--radius); padding: 12px 14px; margin-bottom: 20px;
          ">
            <div style="font-family: var(--font-mono); font-size: 11px; font-weight: 700;
                        text-transform: uppercase; letter-spacing: 0.08em;
                        color: var(--muted); margin-bottom: 6px;">Account</div>
            <div style="font-size: 13px; color: var(--text);">
              {html.escape(email)}
            </div>
          </div>

          <form method="post" action="/claim/{html.escape(token)}/confirm">
            <button type="submit" class="btn btn-primary">Confirm &amp; claim identity</button>
          </form>
        </div>
      </div>

      <p style="text-align: center; color: var(--muted); font-size: 12px;
                margin-top: 20px;">
        This links your local key to your account permanently.
      </p>
    </main>

    <style>body {{ display: block; padding: 0; }}</style>"""

    return _page_shell("Authsome — Claim identity", "", body)


def input_page(
    session_id: str,
    display_name: str,
    docs_url: str | None,
    fields: list[dict[str, Any]],
    callback_url: str | None = None,
    warning_message: str | None = None,
) -> str:
    """Generate a dynamic input form for provider credentials."""
    required_rows: list[str] = []
    optional_rows: list[str] = []
    for field in fields:
        row = _field_row(field)
        if field.get("default") is None or field.get("name") in {"client_id", "client_secret"}:
            required_rows.append(row)
        else:
            optional_rows.append(row)

    docs = ""
    if docs_url:
        docs = f"""
        <a href="{html.escape(docs_url)}" target="_blank" rel="noreferrer"
           style="font-size: 13px; color: var(--accent); display: inline-flex;
                  align-items: center; gap: 4px; margin-bottom: 20px;">
          Provider documentation ↗
        </a>"""

    callback_block = ""
    if callback_url:
        callback_block = f"""
        <div style="margin-bottom: 20px;">
          <label style="font-family: var(--font-mono); font-size: 11px; font-weight: 700;
                        text-transform: uppercase; letter-spacing: 0.08em;
                        color: var(--muted); margin-bottom: 8px; display: block;">
            OAuth redirect URI
          </label>
          <div style="display: flex; gap: 6px; align-items: stretch;">
            <input type="text" id="cb-uri" value="{html.escape(callback_url)}" readonly>
            <button type="button" onclick="copyUri(this)" class="btn btn-outline"
              style="width: auto; margin: 0; padding: 0 14px; font-size: 13px;
                     white-space: nowrap;">Copy</button>
          </div>
        </div>"""

    warning_block = ""
    if warning_message:
        warning_block = f"""
        <div style="
          margin-bottom: 20px; padding: 12px 14px;
          border: 1px solid rgba(107,79,29,0.6); border-radius: var(--radius);
          background: rgba(245,158,11,0.08); color: #f7d08a;
        ">
          <div style="font-size: 12px; font-weight: 600; text-transform: uppercase;
                      letter-spacing: 0.06em; margin-bottom: 4px; color: #f7d08a;">Warning</div>
          <span style="font-size: 13px;">{html.escape(warning_message)}</span>
        </div>"""

    optional_block = ""
    if optional_rows:
        optional_block = f"""
        <details>
          <summary>Advanced options</summary>
          {"".join(optional_rows)}
        </details>"""

    body = f"""
    <main style="
      width: 100%; max-width: 480px; margin: 0 auto;
      padding: 48px 20px 32px;
    ">
      <div style="margin-bottom: 24px;">{_BRAND}</div>

      <div class="panel">
        <div class="panel-header">
          <h1 style="font-size: 18px; font-weight: 600; letter-spacing: -0.01em;
                     margin-bottom: 4px;">{html.escape(display_name)}</h1>
          <p style="color: var(--muted); font-size: 13px; margin: 0;">
            Enter the required credentials to continue.
          </p>
        </div>

        <div class="panel-body">
          {docs}
          {callback_block}
          {warning_block}

          <form method="post" action="/auth/sessions/{html.escape(session_id)}/input">
            {"".join(required_rows)}
            {optional_block}
            <div style="margin-top: 8px;">
              <button type="submit" class="btn btn-primary">Continue</button>
            </div>
          </form>
        </div>
      </div>
    </main>

    <style>body {{ display: block; padding: 0; }}</style>

    {"_copy_uri_script(callback_url)" if callback_url else ""}"""

    script = _copy_uri_script() if callback_url else ""

    body = f"""
    <main style="
      width: 100%; max-width: 480px; margin: 0 auto;
      padding: 48px 20px 32px;
    ">
      <div style="margin-bottom: 24px;">{_BRAND}</div>

      <div class="panel">
        <div class="panel-header">
          <h1 style="font-size: 18px; font-weight: 600; letter-spacing: -0.01em;
                     margin-bottom: 4px;">{html.escape(display_name)}</h1>
          <p style="color: var(--muted); font-size: 13px; margin: 0;">
            Enter the required credentials to continue.
          </p>
        </div>

        <div class="panel-body">
          {docs}
          {callback_block}
          {warning_block}

          <form method="post" action="/auth/sessions/{html.escape(session_id)}/input">
            {"".join(required_rows)}
            {optional_block}
            <div style="margin-top: 8px;">
              <button type="submit" class="btn btn-primary">Continue</button>
            </div>
          </form>
        </div>
      </div>
    </main>

    <style>body {{ display: block; padding: 0; }}</style>
    {script}"""

    return _page_shell(f"Authsome — {html.escape(display_name)}", "", body)


def _copy_uri_script() -> str:
    return """<script>
      function copyUri(btn) {
        var el = document.getElementById("cb-uri");
        el.select(); el.setSelectionRange(0, 99999);
        navigator.clipboard.writeText(el.value).catch(() => {
          document.execCommand("copy");
        });
        var orig = btn.innerText;
        btn.innerText = "Copied!";
        btn.style.borderColor = "var(--accent)";
        setTimeout(() => { btn.innerText = orig; btn.style.borderColor = ""; }, 2000);
      }
    </script>"""


def _field_row(field: dict[str, Any]) -> str:
    name = html.escape(str(field["name"]))
    label = html.escape(str(field["label"]))
    input_type = "password" if field.get("secret", True) else "text"
    value = html.escape(str(field.get("default") or ""))
    required = " required" if field.get("default") is None else ""
    pattern = f' pattern="{html.escape(str(field["pattern"]))}"' if field.get("pattern") else ""
    hint = ""
    if field.get("pattern_hint"):
        hint = f"<small>{html.escape(str(field['pattern_hint']))}</small>"
    return (
        f'<div class="field-group">'
        f'<label for="{name}">{label}</label>'
        f'<input id="{name}" type="{input_type}" name="{name}"'
        f' value="{value}"{required}{pattern}>'
        f"{hint}</div>"
    )


def device_code_page(
    display_name: str,
    user_code: str,
    verification_uri: str,
    verification_uri_complete: str | None,
) -> str:
    """Generate a device code verification page."""
    link = verification_uri_complete or verification_uri
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Authsome — Device login</title>
    {DEVICE_BRIDGE_STYLE}
  </head>
  <body>
    <div class="brand">Authsome<span>.</span></div>
    <h2>{html.escape(display_name)}</h2>
    <p class="subtitle">Enter this code on the login page to complete authentication.</p>

    <div class="code-wrap">
      <input type="text" id="user-code" value="{html.escape(user_code)}" readonly
             aria-label="Device code">
      <button type="button" class="copybtn" onclick="copyCode(this)">Copy</button>
    </div>

    <a href="{html.escape(link)}" target="_blank" class="verify">
      Open login page ↗
    </a>

    <p class="note">After completing login in your browser, return to your terminal.</p>

    <script>
      function legacyCopy(text) {{
        var ta = document.createElement("textarea");
        ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
        document.body.appendChild(ta); ta.focus(); ta.select();
        var ok = false;
        try {{ ok = document.execCommand("copy"); }} catch(e) {{}}
        document.body.removeChild(ta);
        return ok;
      }}
      async function copyCode(btn) {{
        var val = document.getElementById("user-code").value;
        var ok = false;
        if (navigator.clipboard) {{
          try {{ await navigator.clipboard.writeText(val); ok = true; }} catch(e) {{}}
        }}
        if (!ok) ok = legacyCopy(val);
        var orig = btn.innerText;
        btn.innerText = ok ? "Copied!" : "Press Cmd+C";
        if (!ok) window.prompt("Copy this code:", val);
        setTimeout(() => {{ btn.innerText = orig; }}, 2000);
      }}
    </script>
  </body>
</html>"""
