"""Web UI themes and styles for Authsome local server."""

from __future__ import annotations

DARK_THEME_CSS = """
:root {
  color-scheme: dark;
  --bg: #000000;
  --panel: #0a0a0a;
  --text: #ededed;
  --muted: #a1a1aa;
  --line: #27272a;
  --accent: #83ca16;
  --focus: var(--accent);
  --primary: #ededed;
  --primary-text: #000000;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  background: var(--bg);
  color: var(--text);
  font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  -webkit-font-smoothing: antialiased;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
main {
  width: 100%;
  max-width: 440px;
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 32px;
}
h1 {
  margin: 0 0 4px;
  font-size: 20px;
  font-weight: 500;
  letter-spacing: -0.02em;
}
p {
  margin: 0 0 24px;
  color: var(--muted);
  font-size: 14px;
}
a {
  color: var(--text);
  text-decoration: none;
}
a:hover { color: var(--accent); }
form { margin-top: 16px; }
.field-group { margin-bottom: 16px; }
label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 6px;
  color: var(--text);
}
input {
  width: 100%;
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: 6px;
  color: var(--text);
  font-family: inherit;
  font-size: 14px;
  padding: 10px 12px;
  transition: border-color 0.15s;
}
input:focus {
  outline: none;
  border-color: var(--focus);
}
small {
  display: block;
  margin-top: 6px;
  color: var(--muted);
  font-size: 12px;
}
button {
  width: 100%;
  background: var(--primary);
  color: var(--primary-text);
  border: none;
  border-radius: 6px;
  padding: 10px 12px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  margin-top: 12px;
  transition: opacity 0.15s;
}
button:hover { opacity: 0.9; }
details {
  margin: 24px 0;
}
summary {
  font-size: 13px;
  font-weight: 500;
  color: var(--muted);
  cursor: pointer;
  user-select: none;
  transition: color 0.15s;
}
summary:hover {
  color: var(--accent);
}
details[open] summary { margin-bottom: 16px; }
"""

DEVICE_BRIDGE_STYLE = """
<style>
:root {
  color-scheme: dark;
  --bg: #000000;
  --panel: #0a0a0a;
  --text: #ededed;
  --muted: #a1a1aa;
  --line: #27272a;
  --accent: #83ca16;
  --focus: var(--accent);
  --primary: #ededed;
  --primary-text: #000000;
}
.brand {
  margin-bottom: 24px;
  color: var(--muted);
  font-size: 13px;
  font-weight: 500;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.brand::after {
  content: ".";
  color: var(--accent);
}
body {
  font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  max-width: 420px;
  margin: 0 auto;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 40px 20px;
  background: var(--bg);
  color: var(--text);
  -webkit-font-smoothing: antialiased;
}
h2 { margin: 0 0 8px; font-size: 20px; font-weight: 500; letter-spacing: -0.02em; }
.subtitle { color: var(--muted); margin-bottom: 32px; font-size: 14px; line-height: 1.5; }
.code-wrap { display: flex; gap: 8px; align-items: stretch; margin-bottom: 24px; }
.code-wrap input {
  flex: 1;
  font-size: 24px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  padding: 12px;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--panel);
  color: var(--text);
  text-align: center;
  letter-spacing: 2px;
  box-sizing: border-box;
}
.code-wrap input:focus { outline: none; border-color: var(--focus); }
.copybtn {
  padding: 0 20px;
  font-size: 14px;
  border: 1px solid var(--line);
  background: var(--panel);
  color: var(--text);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
  font-weight: 500;
}
.copybtn:hover { background: #111111; border-color: var(--accent); }
a.verify {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 24px;
  padding: 12px 16px;
  background: var(--primary);
  color: var(--primary-text);
  text-decoration: none;
  border-radius: 6px;
  font-weight: 500;
  transition: opacity 0.15s;
  width: 100%;
  text-align: center;
  box-sizing: border-box;
}
a.verify:hover { opacity: 0.9; }
.note { font-size: 13px; color: var(--muted); text-align: center; line-height: 1.5; }
</style>
"""
