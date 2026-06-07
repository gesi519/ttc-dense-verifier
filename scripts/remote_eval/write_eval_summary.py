from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Write final TTC evaluation summary from exported CSV assets.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cfg = _read_json(Path(args.config))
    paths = cfg["paths"]
    table1 = _read_csv(Path(paths["overall_table"]))
    table2 = _read_csv(Path(paths["error_table"]))
    table3 = _read_csv(Path(paths["latency_table"]))
    static_summary = _read_json(Path(paths["static_summary"]))
    merge_report = _read_json(Path(paths["merge_report"]))

    metrics_path = Path(paths["metrics_csv"])
    main_results_path = Path(paths["main_results_md"])
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    main_results_path.parent.mkdir(parents=True, exist_ok=True)

    metrics_rows = _join_metric_rows(table1, table2, table3)
    metadata = {
        "run_id": cfg["run_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "merge_ok": merge_report.get("ok"),
        "merged_rows": merge_report.get("merged_rows"),
        "method_count": len(metrics_rows),
    }

    if not args.dry_run:
        _write_csv(metrics_path, metrics_rows)
        main_results_path.write_text(
            _render_markdown(metadata, metrics_rows, static_summary, merge_report, cfg),
            encoding="utf-8",
        )
    print(json.dumps({**metadata, "metrics_csv": str(metrics_path), "main_results_md": str(main_results_path)}, ensure_ascii=False, indent=2))
    return 0 if merge_report.get("ok") and metrics_rows else 1


def _join_metric_rows(
    overall_rows: list[dict[str, str]],
    error_rows: list[dict[str, str]],
    latency_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    by_method: dict[str, dict[str, Any]] = {}
    for rows in (overall_rows, error_rows, latency_rows):
        for row in rows:
            method = row.get("method", "")
            current = by_method.setdefault(method, {"method": method})
            for key, value in row.items():
                if key == "method":
                    continue
                current[key] = _parse_number(value)
    return [by_method[key] for key in sorted(by_method)]


def _render_markdown(
    metadata: dict[str, Any],
    metrics_rows: list[dict[str, Any]],
    static_summary: dict[str, Any],
    merge_report: dict[str, Any],
    cfg: dict[str, Any],
) -> str:
    lines = [
        "# TTC Dense Verifier Evaluation",
        "",
        f"- run_id: `{metadata['run_id']}`",
        f"- created_at: `{metadata['created_at']}`",
        f"- git_commit: `{metadata['git_commit']}`",
        f"- merged_rows: `{merge_report.get('merged_rows')}`",
        f"- merge_ok: `{merge_report.get('ok')}`",
        "",
        "## Main Metrics",
        "",
        _markdown_table(metrics_rows),
        "",
        "## Static Metric Summary",
        "",
        "```json",
        json.dumps(static_summary, ensure_ascii=False, indent=2, sort_keys=True),
        "```",
        "",
        "## Artifacts",
        "",
        f"- merged_output: `{cfg['paths']['merged_output']}`",
        f"- metrics_csv: `{cfg['paths']['metrics_csv']}`",
        f"- human_review_csv: `{cfg['paths']['human_review_csv']}`",
        f"- judge_requests: `{cfg['paths']['judge_requests']}`",
        f"- figures_dir: `{cfg['paths']['figures_dir']}`",
        "",
        "## Notes",
        "",
        "Static metrics are automatic checks for visible formatting and writing defects. They do not replace human or model-judge evaluation of technical correctness.",
        "All three methods use the same 500 test prompts.",
        "",
    ]
    return "\n".join(lines)


def _markdown_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    preferred = [
        "method",
        "count",
        "abnormal_symbol_count_mean",
        "code_fence_mismatch_mean",
        "slogan_phrase_count_mean",
        "word_count_mean",
        "abnormal_symbol_count_total",
        "code_fence_mismatch_total",
        "slogan_phrase_count_total",
        "repeated_line_count_total",
        "latency_ms_mean",
        "verifier_call_count_mean",
    ]
    keys = [key for key in preferred if any(key in row for row in rows)]
    lines = [
        "| " + " | ".join(keys) + " |",
        "| " + " | ".join("---" for _ in keys) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_format_cell(row.get(key, "")) for key in keys) + " |")
    return "\n".join(lines)


def _format_cell(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def _parse_number(value: str) -> Any:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    if number.is_integer():
        return int(number)
    return number


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = sorted({key for row in rows for key in row})
    if "method" in keys:
        keys.remove("method")
        keys.insert(0, "method")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def _git_commit() -> str:
    if not Path(".git/HEAD").exists():
        return "not-a-git-checkout"
    return os.popen("git rev-parse HEAD 2>/dev/null").read().strip() or "unknown"


if __name__ == "__main__":
    raise SystemExit(main())

