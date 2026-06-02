"""Web UI themes and styles for Authsome local server.

Design system: Authsome Secure Console (see src/authsome/ui/DESIGN.md).
Palette: Deep Emerald (#10B981) + Obsidian (#09090B), dark-first.
Fonts: Hanken Grotesk (UI) + JetBrains Mono (data/code).
"""

from __future__ import annotations

_FONT_IMPORT = """
  @import url('https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;500;600&family=JetBrains+Mono:wght@400;500;700&display=swap');
"""

# Core design tokens aligned with DESIGN.md
DESIGN_TOKENS = """
  :root {
    color-scheme: dark;

    /* Surfaces */
    --bg:               #09090b;
    --surface:          #131315;
    --surface-dim:      #0e0e10;
    --surface-high:     #201f22;
    --surface-highest:  #2a2a2c;

    /* Text */
    --text:             #e5e1e4;
    --muted:            #86948a;
    --muted-hi:         #bbcabf;

    /* Borders */
    --line:             #27272a;
    --line-accent:      #3c4a42;

    /* Primary — Emerald */
    --accent:           #10b981;
    --accent-dim:       #4edea3;
    --accent-fg:        #003824;
    --accent-glow:      rgba(16,185,129,0.18);
    --accent-glow-sm:   rgba(16,185,129,0.08);

    /* Error */
    --error:            #ffb4ab;
    --error-bg:         rgba(147,0,10,0.15);
    --error-border:     rgba(147,0,10,0.35);

    /* Typography */
    --font-ui:          'Hanken Grotesk', ui-sans-serif, system-ui, -apple-system, sans-serif;
    --font-mono:        'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;

    /* Radii */
    --radius-sm:        4px;
    --radius:           6px;
    --radius-lg:        8px;
    --radius-xl:        12px;
  }
"""

BASE_RESET = """
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  html { -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }
  body {
    font-family: var(--font-ui);
    font-size: 14px;
    line-height: 1.5;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
  }
  a { color: var(--text); text-decoration: none; }
  a:hover { color: var(--accent); }
"""

FORM_ELEMENTS = """
  label {
    display: block;
    font-size: 13px;
    font-weight: 500;
    color: var(--muted-hi);
    margin-bottom: 6px;
    letter-spacing: 0.01em;
  }
  input[type="email"],
  input[type="password"],
  input[type="text"] {
    width: 100%;
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    color: var(--text);
    font-family: var(--font-ui);
    font-size: 14px;
    padding: 9px 12px;
    transition: border-color 0.15s ease, box-shadow 0.15s ease;
    outline: none;
  }
  input[type="email"]:focus,
  input[type="password"]:focus,
  input[type="text"]:focus {
    border-color: var(--accent);
    box-shadow: 0 0 0 2px var(--accent-glow);
  }
  input[readonly] {
    color: var(--accent-dim);
    font-family: var(--font-mono);
    font-size: 13px;
    cursor: default;
  }
  small {
    display: block;
    margin-top: 5px;
    color: var(--muted);
    font-size: 12px;
    line-height: 1.4;
  }
  .field-group { margin-bottom: 14px; }
"""

BTN_PRIMARY = """
  .btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    font-family: var(--font-ui);
    font-size: 14px;
    font-weight: 500;
    border-radius: var(--radius);
    padding: 9px 16px;
    cursor: pointer;
    border: 1px solid transparent;
    transition: opacity 0.15s ease, box-shadow 0.15s ease, background 0.15s ease;
    width: 100%;
  }
  .btn-primary {
    background: var(--accent);
    color: var(--accent-fg);
    border-color: var(--accent);
    box-shadow: 0 0 20px -8px var(--accent);
  }
  .btn-primary:hover {
    opacity: 0.88;
    box-shadow: 0 0 28px -6px var(--accent);
  }
  .btn-outline {
    background: transparent;
    color: var(--text);
    border-color: var(--line);
  }
  .btn-outline:hover {
    border-color: var(--accent);
    background: var(--accent-glow-sm);
    color: var(--text);
  }
  .btn-ghost {
    background: transparent;
    color: var(--muted-hi);
    border-color: transparent;
    width: auto;
  }
  .btn-ghost:hover {
    color: var(--text);
    background: var(--surface-high);
  }
"""

PANEL = """
  .panel {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: var(--radius-lg);
  }
  .panel-header {
    padding: 20px 24px 16px;
    border-bottom: 1px solid var(--line);
  }
  .panel-body { padding: 20px 24px; }
"""

DETAILS_SUMMARY = """
  details { margin: 20px 0; }
  summary {
    font-size: 13px;
    font-weight: 500;
    color: var(--muted);
    cursor: pointer;
    user-select: none;
    transition: color 0.15s;
    list-style: none;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  summary::-webkit-details-marker { display: none; }
  summary::before {
    content: '›';
    font-size: 16px;
    transition: transform 0.15s;
    color: var(--muted);
  }
  details[open] summary::before { transform: rotate(90deg); }
  summary:hover { color: var(--accent-dim); }
  details[open] summary { margin-bottom: 14px; }
"""

# The primary CSS block used across all auth/interstitial pages
DARK_THEME_CSS = _FONT_IMPORT + DESIGN_TOKENS + BASE_RESET + FORM_ELEMENTS + BTN_PRIMARY + PANEL + DETAILS_SUMMARY

# Standalone device/bridge page style (self-contained for <style> tag)
DEVICE_BRIDGE_STYLE = f"""<style>
{_FONT_IMPORT}
{DESIGN_TOKENS}
{BASE_RESET}
{BTN_PRIMARY}

body {{
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  justify-content: center;
  min-height: 100vh;
  padding: 40px 20px;
  max-width: 420px;
  margin: 0 auto;
}}
.brand {{
  font-family: var(--font-mono);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 32px;
}}
.brand span {{ color: var(--accent); }}
h2 {{ font-size: 22px; font-weight: 600; letter-spacing: -0.02em; margin-bottom: 8px; }}
.subtitle {{ color: var(--muted); font-size: 14px; line-height: 1.6; margin-bottom: 28px; }}
.code-wrap {{
  display: flex;
  gap: 8px;
  align-items: stretch;
  margin-bottom: 20px;
  width: 100%;
}}
.code-wrap input {{
  flex: 1;
  font-size: 22px;
  font-family: var(--font-mono);
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
  text-align: center;
  letter-spacing: 0.12em;
  outline: none;
}}
.code-wrap input:focus {{ border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-glow); }}
.copybtn {{
  padding: 0 18px;
  font-size: 13px;
  font-family: var(--font-ui);
  font-weight: 500;
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--text);
  border-radius: var(--radius);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;
  white-space: nowrap;
}}
.copybtn:hover {{ border-color: var(--accent); background: var(--accent-glow-sm); }}
a.verify {{
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 20px;
  padding: 10px 16px;
  background: var(--accent);
  color: var(--accent-fg);
  text-decoration: none;
  border-radius: var(--radius);
  font-weight: 500;
  font-size: 14px;
  transition: opacity 0.15s;
  width: 100%;
  box-shadow: 0 0 20px -8px var(--accent);
}}
a.verify:hover {{ opacity: 0.88; }}
.note {{ font-size: 13px; color: var(--muted); text-align: center; line-height: 1.5; }}
</style>"""
