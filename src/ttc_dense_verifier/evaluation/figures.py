from __future__ import annotations

import html
from collections import defaultdict
from pathlib import Path
from typing import Any

from ttc_dense_verifier.evaluation.reports import write_csv


def build_architecture_mermaid() -> str:
    return "\n".join(
        [
            "flowchart LR",
            '  prompts["C/System Prompts"] --> generator["Frozen Qwen2.5-32B Generator"]',
            '  prompts --> data["Synthetic Preference Data"]',
            '  data --> verifier["Dense Qwen2.5-7B Verifier"]',
            '  generator --> controller["Beam Search / MCTS Controller"]',
            '  verifier --> controller',
            '  controller --> outputs["TTC Inference Logs"]',
            '  outputs --> eval["Evaluation Tables and Figures"]',
            '  eval --> demo["Classroom Demo"]',
        ]
    )


def build_decoding_mermaid(rows: list[dict[str, Any]]) -> str:
    row = rows[0] if rows else {}
    prompt = _label(str(row.get("prompt", "Prompt")))
    final_answer = _label(str(row.get("final_answer", "Final answer")))
    kept = _first_trace_item(row, "kept") or _best_branch(row)
    pruned = _first_trace_item(row, "pruned") or _worst_branch(row)
    kept_text = _label(str(kept.get("text", "Kept branch")))
    pruned_text = _label(str(pruned.get("text", "Pruned branch")))
    kept_score = _score_label(kept)
    pruned_score = _score_label(pruned)

    return "\n".join(
        [
            "flowchart LR",
            f'  prompt["Prompt: {prompt}"] --> expand["Generator expands candidate branches"]',
            f'  expand --> kept["Active Branch: {kept_text}"]',
            f'  expand --> pruned["Pruned Branch: {pruned_text}"]',
            f'  kept --> kept_score["Verifier Score: {kept_score}"]',
            f'  pruned --> pruned_score["Verifier Score: {pruned_score}"]',
            '  kept_score --> select["Keep top-scoring branch"]',
            '  pruned_score -. below beam cutoff .-> discard["Discard"]',
            f'  select --> final["Final Answer: {final_answer}"]',
        ]
    )


def build_quality_compute_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row.get("method", "unknown")), _compute_budget(row))].append(row)

    table: list[dict[str, Any]] = []
    for (method, compute_budget), group_rows in sorted(grouped.items()):
        table.append(
            {
                "method": method,
                "compute_budget": compute_budget,
                "count": len(group_rows),
                "final_score_mean": _mean([_numeric(row.get("final_score")) for row in group_rows]),
                "verifier_call_count_mean": _mean([_numeric(row.get("verifier_call_count")) for row in group_rows]),
                "latency_ms_mean": _mean([_numeric(row.get("latency_ms")) for row in group_rows]),
            }
        )
    return table


def build_case_study_markdown(row: dict[str, Any]) -> str:
    branch_rows = []
    for index, branch in enumerate(row.get("branch_scores", []), start=1):
        branch_rows.append(
            "| {index} | {reward} | {score} | {text} |".format(
                index=index,
                reward=_format_number(_numeric(branch.get("verifier_reward"))),
                score=_format_number(_numeric(branch.get("total_score"))),
                text=_escape_table(str(branch.get("text", ""))),
            )
        )
    if not branch_rows:
        branch_rows.append("| 1 | 0 | 0 | No branch scores recorded. |")

    return "\n".join(
        [
            "# Figure 4: Qualitative Case Study",
            "",
            f"Prompt ID: `{row.get('prompt_id', '')}`",
            "",
            "## Prompt",
            "",
            str(row.get("prompt", "")),
            "",
            "## Final Answer",
            "",
            str(row.get("final_answer", "")),
            "",
            "## Branch Scores",
            "",
            "| Branch | Verifier Reward | Total Score | Text |",
            "|---:|---:|---:|---|",
            *branch_rows,
            "",
        ]
    )


def write_paper_figures(output_dir: str | Path, rows: list[dict[str, Any]]) -> None:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "figure1_architecture.mmd").write_text(build_architecture_mermaid(), encoding="utf-8")
    (output_path / "figure2_ttc_decoding.mmd").write_text(build_decoding_mermaid(rows), encoding="utf-8")
    write_csv(output_path / "figure3_quality_vs_compute.csv", build_quality_compute_rows(rows))
    case_row = _select_case_study_row(rows)
    (output_path / "figure4_case_study.md").write_text(build_case_study_markdown(case_row), encoding="utf-8")


def _select_case_study_row(rows: list[dict[str, Any]]) -> dict[str, Any]:
    for row in rows:
        if row.get("branch_scores"):
            return row
    return rows[0] if rows else {}


def _first_trace_item(row: dict[str, Any], key: str) -> dict[str, Any]:
    for trace in row.get("step_traces", []):
        values = trace.get(key, [])
        if values:
            return dict(values[0])
    return {}


def _best_branch(row: dict[str, Any]) -> dict[str, Any]:
    branches = [dict(branch) for branch in row.get("branch_scores", [])]
    if not branches:
        return {}
    return max(branches, key=lambda branch: _numeric(branch.get("total_score")))


def _worst_branch(row: dict[str, Any]) -> dict[str, Any]:
    branches = [dict(branch) for branch in row.get("branch_scores", [])]
    if not branches:
        return {}
    return min(branches, key=lambda branch: _numeric(branch.get("total_score")))


def _compute_budget(row: dict[str, Any]) -> str:
    params = row.get("decoding_parameters", {})
    if not isinstance(params, dict) or not params:
        return "default"
    return "; ".join(f"{key}={params[key]}" for key in sorted(params))


def _score_label(branch: dict[str, Any]) -> str:
    if "total_score" in branch:
        return _format_number(_numeric(branch.get("total_score")))
    if "verifier_reward" in branch:
        return _format_number(_numeric(branch.get("verifier_reward")))
    return "not recorded"


def _label(value: str, max_length: int = 80) -> str:
    collapsed = " ".join(value.split())
    if len(collapsed) > max_length:
        collapsed = collapsed[: max_length - 3].rstrip() + "..."
    return html.escape(collapsed, quote=True)


def _escape_table(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def _numeric(value: Any) -> float:
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _format_number(value: float) -> str:
    return f"{value:.4g}"
