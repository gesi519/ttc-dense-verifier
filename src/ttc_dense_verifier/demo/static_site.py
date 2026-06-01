from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any


def render_demo_page(records: list[dict[str, Any]], *, title: str = "TTC Dense Verifier Demo") -> str:
    cases = "\n".join(_render_case(record, index) for index, record in enumerate(records, start=1))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17202a;
      --muted: #5f6c7b;
      --line: #d7dee8;
      --panel: #ffffff;
      --surface: #f6f8fb;
      --kept: #0f766e;
      --pruned: #b42318;
      --accent: #315b91;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--ink);
      background: var(--surface);
      line-height: 1.5;
    }}
    header {{
      padding: 28px clamp(18px, 4vw, 52px) 16px;
      border-bottom: 1px solid var(--line);
      background: #fff;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: clamp(26px, 3vw, 40px);
      letter-spacing: 0;
    }}
    .subhead {{
      margin: 0;
      max-width: 980px;
      color: var(--muted);
      font-size: 15px;
    }}
    main {{
      width: min(1180px, calc(100vw - 28px));
      margin: 22px auto 48px;
      display: grid;
      gap: 18px;
    }}
    .case {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    .case-header {{
      display: flex;
      gap: 16px;
      justify-content: space-between;
      align-items: start;
      padding: 16px 18px;
      border-bottom: 1px solid var(--line);
    }}
    .case-title {{
      margin: 0;
      font-size: 18px;
    }}
    .metrics {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: flex-end;
      min-width: 220px;
    }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 4px 8px;
      font-size: 13px;
      color: var(--muted);
      background: #fafbfc;
    }}
    .case-grid {{
      display: grid;
      grid-template-columns: minmax(0, 0.9fr) minmax(0, 1.1fr);
      gap: 0;
    }}
    .pane {{
      padding: 16px 18px;
      border-right: 1px solid var(--line);
      min-width: 0;
    }}
    .pane:last-child {{ border-right: 0; }}
    h3 {{
      margin: 0 0 8px;
      font-size: 13px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    .text-block {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      margin: 0 0 16px;
      font-size: 14px;
    }}
    .branch-list {{
      display: grid;
      gap: 8px;
      margin: 0;
      padding: 0;
      list-style: none;
    }}
    .branch {{
      border: 1px solid var(--line);
      border-left-width: 4px;
      border-radius: 6px;
      padding: 10px 12px;
      background: #fff;
    }}
    .branch.kept {{ border-left-color: var(--kept); }}
    .branch.pruned {{ border-left-color: var(--pruned); }}
    .branch-top {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 6px;
      color: var(--muted);
      font-size: 13px;
    }}
    .score {{
      font-variant-numeric: tabular-nums;
      color: var(--accent);
      white-space: nowrap;
    }}
    @media (max-width: 760px) {{
      .case-header, .case-grid {{ display: block; }}
      .metrics {{ justify-content: flex-start; margin-top: 10px; }}
      .pane {{ border-right: 0; border-bottom: 1px solid var(--line); }}
      .pane:last-child {{ border-bottom: 0; }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>{escape(title)}</h1>
    <p class="subhead">Frozen generator candidates are scored by a separate verifier; low-scoring branches are removed before final selection.</p>
  </header>
  <main>
    {cases}
  </main>
</body>
</html>
"""


def write_demo_page(path: str | Path, records: list[dict[str, Any]], *, title: str = "TTC Dense Verifier Demo") -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_demo_page(records, title=title), encoding="utf-8")


def _render_case(record: dict[str, Any], index: int) -> str:
    prompt_id = escape(str(record.get("prompt_id", f"case-{index}")))
    prompt = escape(str(record.get("prompt", "")))
    method = escape(str(record.get("method", "unknown")))
    final_answer = escape(str(record.get("final_answer", record.get("answer", ""))))
    final_score = _format_score(record.get("final_score", 0))
    verifier_calls = escape(str(record.get("verifier_call_count", 0)))
    kept_html, pruned_html = _render_branch_groups(record)
    return f"""<article class="case">
  <div class="case-header">
    <div>
      <h2 class="case-title">{index}. {prompt_id}</h2>
      <div class="metric">{method}</div>
    </div>
    <div class="metrics">
      <span class="metric">Final score {final_score}</span>
      <span class="metric">Verifier calls {verifier_calls}</span>
    </div>
  </div>
  <div class="case-grid">
    <section class="pane">
      <h3>Prompt</h3>
      <p class="text-block">{prompt}</p>
      <h3>Final selected answer</h3>
      <p class="text-block">{final_answer}</p>
    </section>
    <section class="pane">
      <h3>Kept branches</h3>
      {kept_html}
      <h3>Pruned branches</h3>
      {pruned_html}
    </section>
  </div>
</article>"""


def _render_branch_groups(record: dict[str, Any]) -> tuple[str, str]:
    kept: list[dict[str, Any]] = []
    pruned: list[dict[str, Any]] = []
    for step in record.get("step_traces", []):
        kept.extend(step.get("kept", []))
        pruned.extend(step.get("pruned", []))
    if not kept:
        kept = list(record.get("branch_scores", []))
    return _render_branches(kept, "kept"), _render_branches(pruned, "pruned")


def _render_branches(branches: list[dict[str, Any]], branch_class: str) -> str:
    if not branches:
        return '<p class="text-block">No branches recorded.</p>'
    items = []
    for branch in branches:
        text = escape(str(branch.get("text", "")))
        total_score = _format_score(branch.get("total_score", 0))
        verifier_reward = _format_score(branch.get("verifier_reward", branch.get("total_score", 0)))
        items.append(
            f"""<li class="branch {branch_class}">
  <div class="branch-top"><span>{escape(branch_class.title())}</span><span class="score">score {total_score} / verifier {verifier_reward}</span></div>
  <div class="text-block">{text}</div>
</li>"""
        )
    return f"""<ul class="branch-list">
{''.join(items)}
</ul>"""


def _format_score(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "0.00"
