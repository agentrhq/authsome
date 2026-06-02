#!/usr/bin/env python3
"""Generate an HTML report from a grading.json produced by run_evals.py.

Usage:
    uv run python evals/generate_report.py evals/results/<timestamp>/grading.json
"""

import argparse
import html
import json
import subprocess
from pathlib import Path


def verdict_icon(passed: bool | None) -> tuple[str, str]:
    """Return (icon, css_class) for a passed value."""
    if passed is True:
        return "✓", "pass"
    if passed is False:
        return "✗", "fail"
    return "—", "skip"


def generate_html(data: dict) -> str:
    summary = data["summary"]
    results = data["results"]
    skill_name = data.get("skill_name", "authsome")
    timestamp = data.get("timestamp", "")

    font_url = "https://fonts.googleapis.com/css2?family=Poppins:wght@500;600&family=Lora:wght@400;500&display=swap"

    parts = [
        f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(skill_name)} — Eval Report</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="{font_url}" rel="stylesheet">
  <style>
    :root {{
      --bg: #faf9f5;
      --surface: #ffffff;
      --border: #e8e6dc;
      --text: #141413;
      --text-muted: #b0aea5;
      --header-bg: #141413;
      --header-text: #faf9f5;
      --green: #788c5d;
      --green-bg: #eef2e8;
      --red: #c44;
      --red-bg: #fceaea;
      --radius: 6px;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Lora', Georgia, serif;
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
    }}
    .header {{
      background: var(--header-bg);
      color: var(--header-text);
      padding: 1rem 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .header h1 {{ font-family: 'Poppins', sans-serif; font-size: 1.25rem; font-weight: 600; }}
    .header .meta {{ font-size: 0.8rem; opacity: 0.7; text-align: right; }}
    .summary-bar {{
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 0.75rem 2rem;
      font-family: 'Poppins', sans-serif;
      font-size: 0.875rem;
      display: flex;
      gap: 1.5rem;
      align-items: center;
    }}
    .chip {{
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.2rem 0.6rem;
      border-radius: 4px;
      font-weight: 600;
    }}
    .chip-pass {{ background: var(--green-bg); color: var(--green); }}
    .chip-fail {{ background: var(--red-bg); color: var(--red); }}
    .chip-skip {{ background: #f5f5f0; color: var(--text-muted); }}
    .main {{ padding: 1.5rem 2rem; display: flex; flex-direction: column; gap: 1rem; }}
    .card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      overflow: hidden;
    }}
    .card-header {{
      display: flex;
      align-items: center;
      gap: 1rem;
      padding: 0.75rem 1rem;
      border-bottom: 1px solid var(--border);
      font-family: 'Poppins', sans-serif;
      font-size: 0.875rem;
    }}
    .eval-id {{ font-size: 0.75rem; color: var(--text-muted); min-width: 2rem; }}
    .eval-name {{ font-weight: 600; flex: 1; }}
    .agent-badge {{
      font-size: 0.7rem;
      padding: 0.15rem 0.5rem;
      border-radius: 3px;
      background: #f0f0e8;
      color: var(--text-muted);
      font-family: monospace;
    }}
    .human-badge {{
      font-size: 0.7rem;
      padding: 0.15rem 0.5rem;
      border-radius: 3px;
      background: #fff3e0;
      color: #b45309;
    }}
    .verdict-icons {{ display: flex; gap: 0.75rem; }}
    .verdict-block {{ display: flex; align-items: center; gap: 0.3rem; font-size: 0.8rem; }}
    .verdict-label {{ color: var(--text-muted); font-size: 0.7rem; }}
    .icon {{ font-size: 1.1rem; font-weight: bold; }}
    .pass {{ color: var(--green); }}
    .fail {{ color: var(--red); }}
    .skip {{ color: var(--text-muted); }}
    .card-body {{
      padding: 0.75rem 1rem;
      font-size: 0.875rem;
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
    }}
    .field-row {{ display: flex; gap: 0.75rem; }}
    .field-label {{
      color: var(--text-muted);
      font-size: 0.75rem;
      min-width: 6rem;
      padding-top: 0.1rem;
      flex-shrink: 0;
    }}
    .field-value {{ flex: 1; line-height: 1.5; }}
    .evidence {{ font-style: italic; color: #555; }}
    details summary {{ cursor: pointer; color: var(--text-muted); font-size: 0.8rem; list-style: none; }}
    details summary::before {{ content: '▶ '; font-size: 0.6rem; }}
    details[open] summary::before {{ content: '▼ '; }}
    details[open] summary {{ margin-bottom: 0.4rem; }}
  </style>
</head>
<body>
  <div class="header">
    <h1>{html.escape(skill_name)} — Eval Report</h1>
    <div class="meta">{html.escape(timestamp)}</div>
  </div>
  <div class="summary-bar">
    <span>Results:</span>
    <span class="chip chip-pass">✓ {summary["passed"]} passed</span>
    <span class="chip chip-fail">✗ {summary["failed"]} failed</span>
    <span class="chip chip-skip">— {summary["skipped"]} skipped</span>
    <span style="color:var(--text-muted)">of {summary["total"]} total</span>
  </div>
  <div class="main">
"""
    ]

    for r in results:
        outcome = r.get("outcome", {})
        traj = r.get("trajectory_efficiency", {})
        o_icon, o_cls = verdict_icon(outcome.get("passed"))
        t_icon, t_cls = verdict_icon(traj.get("passed"))
        is_skipped = r.get("status") == "skipped"
        human = r.get("requires_human", False)

        human_badge = "<span class='human-badge'>human</span>" if human else ""
        env_text = html.escape(r.get("environment", ""))
        state_text = html.escape(r.get("authsome_state", ""))
        prompt_text = html.escape(r["prompt"])
        name_text = html.escape(r.get("name", r["prompt"]))
        agent_text = html.escape(r.get("agent", "claude"))

        if is_skipped:
            body_rows = (
                "<div class='field-row'>"
                "<span class='field-label'>skipped</span>"
                "<span class='field-value evidence'>"
                "Rate limit hit — switch model and retry"
                "</span></div>"
            )
        else:
            o_evidence = html.escape(outcome.get("evidence", ""))
            t_evidence = html.escape(traj.get("evidence", ""))
            body_rows = f"""<div class="field-row">
          <span class="field-label">outcome</span>
          <span class="field-value evidence">{o_evidence}</span>
        </div>
        <div class="field-row">
          <span class="field-label">trajectory</span>
          <span class="field-value evidence">{t_evidence}</span>
        </div>"""

        parts.append(f"""    <div class="card">
      <div class="card-header">
        <span class="eval-id">#{r["id"]}</span>
        <span class="eval-name">{name_text}</span>
        <span class="agent-badge">{agent_text}</span>
        {human_badge}
        <div class="verdict-icons">
          <div class="verdict-block">
            <span class="verdict-label">outcome</span>
            <span class="icon {o_cls}">{o_icon}</span>
          </div>
          <div class="verdict-block">
            <span class="verdict-label">trajectory</span>
            <span class="icon {t_cls}">{t_icon}</span>
          </div>
        </div>
      </div>
      <div class="card-body">
        <div class="field-row">
          <span class="field-label">prompt</span>
          <span class="field-value">{prompt_text}</span>
        </div>
        <details>
          <summary>environment</summary>
          <div class="field-row">
            <span class="field-label"></span>
            <span class="field-value">{env_text}</span>
          </div>
        </details>
        <details>
          <summary>authsome state at start</summary>
          <div class="field-row">
            <span class="field-label"></span>
            <span class="field-value" style="white-space:pre;font-family:monospace;font-size:0.8rem">{state_text}</span>
          </div>
        </details>
        {body_rows}
      </div>
    </div>
""")

    parts.append("""  </div>
</body>
</html>""")
    return "".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate HTML report from grading.json")
    parser.add_argument("grading_json", help="Path to grading.json")
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="Output HTML path (default: report.html next to grading.json)",
    )
    args = parser.parse_args()

    grading_path = Path(args.grading_json)
    data = json.loads(grading_path.read_text())

    html_out = Path(args.output) if args.output else grading_path.parent / "report.html"
    html_out.write_text(generate_html(data))
    print(f"Report written to {html_out}")

    subprocess.run(["open", str(html_out)], check=False)


if __name__ == "__main__":
    main()
