"""HTML page generators for the Authsome server."""

from __future__ import annotations

import html
from typing import Any

from authsome.server.ui.web_theme import DARK_THEME_CSS, DEVICE_BRIDGE_STYLE


def message_page(title: str, message: str) -> str:
    """Generate a simple message page."""
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(title)}</title>
    <style>{DARK_THEME_CSS}</style>
  </head>
  <body>
    <main>
      <h1>{html.escape(title)}</h1>
      <p>{html.escape(message)}</p>
    </main>
  </body>
</html>"""


def hosted_auth_page(
    *,
    next_url: str,
    active_tab: str = "login",
    identity: str | None = None,
    error: str | None = None,
) -> str:
    """Generate the hosted sign-in/register page."""
    title = "Claim identity" if identity else "Open dashboard"
    subtitle = (
        f"Sign in or create an account to claim <strong>{html.escape(identity)}</strong>."
        if identity
        else "Sign in or create an account to open your Authsome dashboard."
    )
    error_block = f'<p style="color:#ff7b72;margin:0 0 16px;">{html.escape(error)}</p>' if error else ""
    register_hidden = "hidden" if active_tab == "login" else ""
    login_hidden = "hidden" if active_tab == "register" else ""
    login_active = "is-active" if active_tab == "login" else ""
    register_active = "is-active" if active_tab == "register" else ""
    auth_tabs = f"""
        <div class="auth-tabs" role="tablist" aria-label="Authentication mode">
          <button
            class="auth-tab {login_active}"
            type="button"
            data-auth-tab="login"
            role="tab"
            aria-selected="{"true" if active_tab == "login" else "false"}"
          >
            Sign in
          </button>
          <button
            class="auth-tab {register_active}"
            type="button"
            data-auth-tab="register"
            role="tab"
            aria-selected="{"true" if active_tab == "register" else "false"}"
          >
            Create account
          </button>
        </div>"""
    register_panel = f"""
        <div class="auth-panel" data-auth-panel="register" {register_hidden}>
          <h2>Create account</h2>
          {error_block if active_tab == "register" else ""}
          <form method="post" action="/ui/auth/register">
            <input type="hidden" name="next" value="{html.escape(next_url)}">
            <label for="register-email">Email</label>
            <input id="register-email" type="email" name="email" required>
            <label for="register-password">Password</label>
            <input id="register-password" type="password" name="password" required>
            <button type="submit">Create account</button>
          </form>
        </div>"""
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Authsome - {title}</title>
    <style>{DARK_THEME_CSS}
      :root {{ color-scheme: dark; }}
      body {{
        min-height: 100vh;
        margin: 0;
        background:
          radial-gradient(circle at top, rgba(34, 197, 94, 0.18), transparent 34%),
          linear-gradient(180deg, #031006 0%, #000 42%);
      }}
      main {{
        max-width: 460px;
        margin: 0 auto;
        padding: 48px 20px;
      }}
      .auth-shell {{
        border: 1px solid rgba(34, 197, 94, 0.25);
        border-radius: 18px;
        background: rgba(0, 0, 0, 0.92);
        box-shadow: 0 28px 60px rgba(0, 0, 0, 0.55);
        overflow: hidden;
      }}
      .auth-header {{
        padding: 28px 28px 18px;
        border-bottom: 1px solid rgba(34, 197, 94, 0.18);
      }}
      .auth-kicker {{
        margin: 0 0 10px;
        color: var(--accent);
        font-size: 12px;
        letter-spacing: 0.18em;
        text-transform: uppercase;
      }}
      .auth-header h1 {{ margin: 0 0 10px; }}
      .auth-header p {{ margin: 0; color: var(--muted); }}
      .auth-tabs {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
        padding: 18px 28px 0;
      }}
      .auth-tab {{
        appearance: none;
        border: 1px solid rgba(34, 197, 94, 0.18);
        border-radius: 999px;
        background: rgba(8, 20, 10, 0.84);
        color: var(--muted);
        cursor: pointer;
        font: inherit;
        font-weight: 600;
        padding: 12px 16px;
        transition: 140ms ease;
      }}
      .auth-tab:hover {{ border-color: rgba(34, 197, 94, 0.34); color: var(--text); }}
      .auth-tab.is-active {{
        background: linear-gradient(180deg, rgba(34, 197, 94, 0.18), rgba(10, 26, 12, 0.96));
        border-color: rgba(34, 197, 94, 0.58);
        color: #d3f9dd;
        box-shadow: inset 0 0 0 1px rgba(34, 197, 94, 0.18);
      }}
      .auth-panel {{
        padding: 24px 28px 28px;
      }}
      .auth-panel h2 {{ margin: 0 0 16px; font-size: 15px; font-weight: 600; }}
      .auth-panel[hidden] {{ display: none; }}
      .auth-panel button[type="submit"] {{ margin-top: 18px; width: 100%; }}
    </style>
  </head>
  <body>
    <main>
      <section class="auth-shell">
        <header class="auth-header">
          <p class="auth-kicker">Authsome Hosted</p>
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </header>
        {auth_tabs}
        <div class="auth-panel" data-auth-panel="login" {login_hidden}>
          <h2>Welcome back</h2>
          {error_block if active_tab == "login" else ""}
          <form method="post" action="/ui/auth/login">
            <input type="hidden" name="next" value="{html.escape(next_url)}">
            <label for="login-email">Email</label>
            <input id="login-email" type="email" name="email" required>
            <label for="login-password">Password</label>
            <input id="login-password" type="password" name="password" required>
            <button type="submit">Sign in</button>
          </form>
        </div>
        {register_panel}
      </section>
    </main>
    <script>
      const tabs = document.querySelectorAll("[data-auth-tab]");
      const panels = document.querySelectorAll("[data-auth-panel]");
      function setTab(name) {{
        tabs.forEach((tab) => {{
          const active = tab.dataset.authTab === name;
          tab.classList.toggle("is-active", active);
          tab.setAttribute("aria-selected", active ? "true" : "false");
        }});
        panels.forEach((panel) => {{
          panel.hidden = panel.dataset.authPanel !== name;
        }});
      }}
      tabs.forEach((tab) => {{
        tab.addEventListener("click", () => setTab(tab.dataset.authTab));
      }});
      setTab("{"register" if active_tab == "register" else "login"}");
    </script>
  </body>
</html>"""


def hosted_claim_auth_page(*, token: str, identity: str, error: str | None = None, active_tab: str = "login") -> str:
    """Generate the hosted sign-in/register page for an identity claim."""
    return hosted_auth_page(
        next_url=f"/ui/claim/{html.escape(token)}",
        active_tab=active_tab,
        identity=identity,
        error=error,
    )


def hosted_claim_confirm_page(*, token: str, identity: str, email: str) -> str:
    """Generate the hosted identity-claim confirmation page."""
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Authsome - Claim identity</title>
    <style>{DARK_THEME_CSS}</style>
  </head>
  <body>
    <main>
      <h1>Claim identity</h1>
      <p>Confirm claiming <strong>{html.escape(identity)}</strong> to <strong>{html.escape(email)}</strong>.</p>
      <form method="post" action="/ui/claim/{html.escape(token)}/confirm">
        <button type="submit">Claim identity</button>
      </form>
    </main>
  </body>
</html>"""


def input_page(
    session_id: str,
    display_name: str,
    docs_url: str | None,
    fields: list[dict[str, Any]],
    callback_url: str | None = None,
    warning_message: str | None = None,
) -> str:
    """Generate a dynamic input form for provider credentials."""
    required_rows = []
    optional_rows = []
    for field in fields:
        row = _field_row(field)
        if field.get("default") is None or field.get("name") == "client_secret":
            required_rows.append(row)
        else:
            optional_rows.append(row)

    docs = (
        f'<p><a href="{html.escape(docs_url)}" target="_blank" rel="noreferrer">Provider documentation</a></p>'
        if docs_url
        else ""
    )

    callback_hint = ""
    if callback_url:
        callback_hint = f"""
        <div style="margin: 16px 0 24px;">
          <label style="font-size: 12px; color: var(--muted); margin-bottom: 6px; display: block;">
            OAuth Redirect URI
          </label>
          <div style="display: flex; gap: 6px; align-items: stretch;">
            <input type="text" id="cb-uri" value="{html.escape(callback_url)}" readonly style="
              flex: 1;
              min-width: 0;
              font-family: ui-monospace, monospace;
              font-size: 13px;
              background: #111;
              color: var(--accent);
              padding: 8px 10px;
              border: 1px solid var(--line);
              border-radius: 6px;
            ">
            <button type="button" onclick="copyUri(this)" style="
              width: auto;
              margin: 0;
              padding: 0 14px;
              font-size: 13px;
              font-weight: 500;
              background: var(--panel);
              border: 1px solid var(--line);
              color: var(--text);
              border-radius: 6px;
              cursor: pointer;
              white-space: nowrap;
            ">Copy</button>
          </div>
        </div>
        """

    optional = ""
    if optional_rows:
        optional = f"<details><summary>Advanced options</summary>{''.join(optional_rows)}</details>"

    warning = ""
    if warning_message:
        warning = f"""
        <div style="
          margin: 16px 0 24px;
          padding: 12px 14px;
          border: 1px solid #6b4f1d;
          border-radius: 8px;
          background: rgba(245, 158, 11, 0.12);
          color: #f7d08a;
        ">
          <strong style="display: block; margin-bottom: 4px;">Warning</strong>
          <span>{html.escape(warning_message)}</span>
        </div>
        """

    script = ""
    if callback_url:
        script = """
    <script>
      function copyUri(btn) {
        var el = document.getElementById("cb-uri");
        el.select();
        el.setSelectionRange(0, 99999);
        navigator.clipboard.writeText(el.value);
        var orig = btn.innerText;
        btn.innerText = "Copied!";
        btn.style.borderColor = "var(--accent)";
        setTimeout(function() {
          btn.innerText = orig;
          btn.style.borderColor = "var(--line)";
        }, 2000);
      }
    </script>"""

    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Authsome - {html.escape(display_name)}</title>
    <style>{DARK_THEME_CSS}</style>
  </head>
  <body>
    <main>
      <h1>{html.escape(display_name)}</h1>
      {docs}
      {callback_hint}
      {warning}
      <form method="post" action="/auth/sessions/{html.escape(session_id)}/input">
        {"".join(required_rows)}
        {optional}
        <button type="submit">Continue</button>
      </form>
    </main>{script}
  </body>
</html>"""


def _field_row(field: dict[str, Any]) -> str:
    name = html.escape(str(field["name"]))
    label = html.escape(str(field["label"]))
    input_type = "password" if field.get("secret", True) else "text"
    value = html.escape(str(field.get("default") or ""))
    required = " required" if field.get("default") is None else ""
    pattern = f' pattern="{html.escape(str(field["pattern"]))}"' if field.get("pattern") else ""
    hint = f"<small>{html.escape(str(field['pattern_hint']))}</small>" if field.get("pattern_hint") else ""
    return (
        f'<div class="field-group">'
        f'<label for="{name}">{label}</label>'
        f'<input id="{name}" type="{input_type}" name="{name}" value="{value}"{required}{pattern}>'
        f"{hint}</div>"
    )


def device_code_page(
    display_name: str,
    user_code: str,
    verification_uri: str,
    verification_uri_complete: str | None,
) -> str:
    """Generate a device code verification page with a premium theme."""
    link = verification_uri_complete or verification_uri
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Authsome - Device Login</title>
    {DEVICE_BRIDGE_STYLE}
  </head>
  <body>
    <div class="brand">Authsome</div>
    <h2>{html.escape(display_name)}</h2>
    <p class="subtitle">Enter the following code on your device to complete the login.</p>
    
    <div class="code-wrap">
      <input type="text" id="user-code" value="{html.escape(user_code)}" readonly>
      <button class="copybtn" onclick="copyCode()">Copy</button>
    </div>
    
    <a href="{html.escape(link)}" target="_blank" class="verify">Open Login Page</a>
    
    <p class="note">
      After completing the login on your device, return to your terminal.
    </p>

    <script>
      function copyCode() {{
        var copyText = document.getElementById("user-code");
        copyText.select();
        copyText.setSelectionRange(0, 99999);
        navigator.clipboard.writeText(copyText.value);
        
        const btn = document.querySelector('.copybtn');
        const originalText = btn.innerText;
        btn.innerText = 'Copied!';
        setTimeout(() => {{
          btn.innerText = originalText;
        }}, 2000);
      }}
    </script>
  </body>
</html>"""
