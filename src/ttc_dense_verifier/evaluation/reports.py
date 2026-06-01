from __future__ import annotations

import csv
from collections import defaultdict
from numbers import Number
from pathlib import Path
from typing import Any

from ttc_dense_verifier.evaluation.metrics import compute_text_metrics


def _answer_text(row: dict[str, Any]) -> str:
    return str(row.get("final_answer", row.get("answer", "")))


def _group_by_method(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("method", "unknown"))].append(row)
    return dict(sorted(grouped.items()))


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def build_overall_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    table: list[dict[str, Any]] = []
    for method, method_rows in _group_by_method(rows).items():
        metrics = [compute_text_metrics(_answer_text(row)) for row in method_rows]
        table.append(
            {
                "method": method,
                "count": len(method_rows),
                "abnormal_symbol_count_mean": _mean([float(item["abnormal_symbol_count"]) for item in metrics]),
                "code_fence_mismatch_mean": _mean([float(item["code_fence_mismatch"]) for item in metrics]),
                "slogan_phrase_count_mean": _mean([float(item["slogan_phrase_count"]) for item in metrics]),
                "word_count_mean": _mean([float(item["word_count"]) for item in metrics]),
            }
        )
    return table


def build_error_breakdown(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    table: list[dict[str, Any]] = []
    for method, method_rows in _group_by_method(rows).items():
        metrics = [compute_text_metrics(_answer_text(row)) for row in method_rows]
        table.append(
            {
                "method": method,
                "abnormal_symbol_count_total": sum(int(item["abnormal_symbol_count"]) for item in metrics),
                "code_fence_mismatch_total": sum(int(item["code_fence_mismatch"]) for item in metrics),
                "slogan_phrase_count_total": sum(int(item["slogan_phrase_count"]) for item in metrics),
                "repeated_line_count_total": sum(int(item["repeated_line_count"]) for item in metrics),
            }
        )
    return table


def build_latency_table(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    table: list[dict[str, Any]] = []
    for method, method_rows in _group_by_method(rows).items():
        table.append(
            {
                "method": method,
                "count": len(method_rows),
                "latency_ms_mean": _mean([_numeric(row.get("latency_ms")) for row in method_rows]),
                "verifier_call_count_mean": _mean([_numeric(row.get("verifier_call_count")) for row in method_rows]),
            }
        )
    return table


def _numeric(value: Any) -> float:
    if isinstance(value, Number):
        return float(value)
    return 0.0


def build_human_review_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_prompt: dict[str, dict[str, Any]] = {}
    for row in rows:
        prompt_id = str(row.get("prompt_id", ""))
        method = str(row.get("method", "unknown"))
        review_row = by_prompt.setdefault(
            prompt_id,
            {
                "prompt_id": prompt_id,
                "prompt": str(row.get("prompt", "")),
                "best_method": "",
                "ttc_removes_visible_defects": "",
                "ttc_loses_useful_information": "",
                "verifier_over_penalizes_valid_wording": "",
                "notes": "",
            },
        )
        review_row[f"{method}_answer"] = _answer_text(row)
    return [by_prompt[key] for key in sorted(by_prompt)]


def build_human_preference_table(review_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reviewed_rows = [row for row in review_rows if str(row.get("best_method", "")).strip()]
    reviewed_count = len(reviewed_rows)
    best_counts: dict[str, int] = defaultdict(int)
    for row in reviewed_rows:
        best_counts[str(row.get("best_method", "")).strip()] += 1

    ttc_removes_count = sum(1 for row in reviewed_rows if _is_yes(row.get("ttc_removes_visible_defects")))
    ttc_loses_count = sum(1 for row in reviewed_rows if _is_yes(row.get("ttc_loses_useful_information")))
    over_penalizes_count = sum(1 for row in reviewed_rows if _is_yes(row.get("verifier_over_penalizes_valid_wording")))

    table: list[dict[str, Any]] = []
    for method in sorted(best_counts):
        table.append(
            {
                "method": method,
                "reviewed_count": reviewed_count,
                "best_count": best_counts[method],
                "preference_rate": best_counts[method] / reviewed_count if reviewed_count else 0.0,
                "ttc_removes_visible_defects_yes_count": ttc_removes_count,
                "ttc_removes_visible_defects_yes_rate": ttc_removes_count / reviewed_count if reviewed_count else 0.0,
                "ttc_loses_useful_information_yes_count": ttc_loses_count,
                "ttc_loses_useful_information_yes_rate": ttc_loses_count / reviewed_count if reviewed_count else 0.0,
                "verifier_over_penalizes_valid_wording_yes_count": over_penalizes_count,
                "verifier_over_penalizes_valid_wording_yes_rate": over_penalizes_count / reviewed_count
                if reviewed_count
                else 0.0,
            }
        )
    return table


def _is_yes(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "是"}


def write_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
