from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ttc_dense_verifier.evaluation.metrics import compute_text_metrics
from ttc_dense_verifier.serving.clients import HTTPVerifierClient


def main() -> int:
    parser = argparse.ArgumentParser(description="Search TTC evaluation criteria using RM validation labels.")
    parser.add_argument("--val-rm", required=True)
    parser.add_argument("--merged-output", required=True)
    parser.add_argument("--score-jsonl", required=True)
    parser.add_argument("--verifier-endpoint", required=True)
    parser.add_argument("--cache-val-scores", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--limit-val", type=int)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "criteria_search_report.md"
    criteria_csv = output_dir / "criteria_grid.csv"
    method_csv = output_dir / "method_scores.csv"

    val_rows = _read_jsonl(Path(args.val_rm))
    if args.limit_val is not None:
        val_rows = val_rows[: args.limit_val]
    merged_rows = _read_jsonl(Path(args.merged_output))
    output_scores = _read_output_scores(Path(args.score_jsonl))

    if args.dry_run:
        print(
            json.dumps(
                {
                    "val_pairs": len(val_rows),
                    "merged_rows": len(merged_rows),
                    "output_score_rows": sum(len(v) for v in output_scores.values()),
                    "output_dir": str(output_dir),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    val_scored = _load_or_score_validation(
        val_rows=val_rows,
        cache_path=Path(args.cache_val_scores),
        endpoint=args.verifier_endpoint,
    )
    criteria_rows = _search_criteria(val_scored)
    chosen_criteria = _choose_criterion(criteria_rows)
    method_rows = _score_methods(merged_rows, output_scores, chosen_criteria)

    _write_csv(criteria_csv, criteria_rows)
    _write_csv(method_csv, method_rows)
    report_path.write_text(
        _render_report(
            val_pairs=len(val_rows),
            criteria_rows=criteria_rows,
            chosen_criteria=chosen_criteria,
            method_rows=method_rows,
            args=args,
            criteria_csv=criteria_csv,
            method_csv=method_csv,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"report": str(report_path), "criteria_csv": str(criteria_csv), "method_csv": str(method_csv)}, ensure_ascii=False, indent=2))
    return 0


def _search_criteria(val_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grid: list[dict[str, float]] = []
    for repeated_penalty in [0.0, 0.1, 0.25, 0.5, 0.75, 1.0]:
        for length_penalty in [0.0, 0.02, 0.05, 0.1, 0.15]:
            for abnormal_penalty in [0.0, 0.5, 1.0, 2.0]:
                grid.append(
                    {
                        "repeated_penalty": repeated_penalty,
                        "length_penalty_per_100_words": length_penalty,
                        "abnormal_penalty": abnormal_penalty,
                    }
                )

    rows: list[dict[str, Any]] = []
    for weights in grid:
        margins = []
        for row in val_rows:
            chosen = _criterion_score(row["chosen_score"], row["chosen_text"], weights)
            rejected = _criterion_score(row["rejected_score"], row["rejected_text"], weights)
            margins.append(chosen - rejected)
        rows.append(
            {
                **weights,
                "pairwise_accuracy": sum(1 for margin in margins if margin > 0) / len(margins),
                "mean_margin": statistics.mean(margins),
                "median_margin": statistics.median(margins),
                "min_margin": min(margins),
            }
        )
    return sorted(rows, key=lambda row: (row["pairwise_accuracy"], row["mean_margin"]), reverse=True)


def _choose_criterion(rows: list[dict[str, Any]]) -> dict[str, Any]:
    # Prefer the strongest validation separator first. This avoids selecting a
    # purely unregularized score when a label-validated defect penalty separates
    # chosen/rejected answers more clearly.
    best_accuracy = max(float(row["pairwise_accuracy"]) for row in rows)
    eligible = [row for row in rows if float(row["pairwise_accuracy"]) >= best_accuracy - 0.002]
    return sorted(
        eligible,
        key=lambda row: (
            -float(row["mean_margin"]),
            float(row["repeated_penalty"]) + float(row["length_penalty_per_100_words"]) + float(row["abnormal_penalty"]),
        ),
    )[0]


def _score_methods(
    rows: list[dict[str, Any]],
    output_scores: dict[str, dict[str, float]],
    criterion: dict[str, Any],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        prompt_id = str(row["prompt_id"])
        method = str(row["method"])
        verifier_score = output_scores[prompt_id][method]
        adjusted = _criterion_score(verifier_score, str(row.get("final_answer", "")), criterion)
        metrics = compute_text_metrics(str(row.get("final_answer", "")))
        grouped[method].append(
            {
                "verifier_score": verifier_score,
                "criterion_score": adjusted,
                "repeated_line_count": metrics["repeated_line_count"],
                "word_count": metrics["word_count"],
                "abnormal_symbol_count": metrics["abnormal_symbol_count"],
                "code_fence_mismatch": metrics["code_fence_mismatch"],
                "slogan_phrase_count": metrics["slogan_phrase_count"],
                "latency_ms": row.get("latency_ms", 0) or 0,
                "verifier_call_count": row.get("verifier_call_count", 0) or 0,
            }
        )

    method_rows: list[dict[str, Any]] = []
    for method, values in sorted(grouped.items()):
        method_rows.append(
            {
                "method": method,
                "count": len(values),
                "criterion_score_mean": _mean([v["criterion_score"] for v in values]),
                "criterion_score_median": statistics.median([v["criterion_score"] for v in values]),
                "verifier_score_mean": _mean([v["verifier_score"] for v in values]),
                "repeated_line_total": sum(int(v["repeated_line_count"]) for v in values),
                "word_count_mean": _mean([v["word_count"] for v in values]),
                "abnormal_symbol_total": sum(int(v["abnormal_symbol_count"]) for v in values),
                "code_fence_mismatch_total": sum(int(v["code_fence_mismatch"]) for v in values),
                "slogan_phrase_total": sum(int(v["slogan_phrase_count"]) for v in values),
                "latency_ms_mean": _mean([float(v["latency_ms"]) for v in values]),
                "verifier_call_count_mean": _mean([float(v["verifier_call_count"]) for v in values]),
            }
        )
    return sorted(method_rows, key=lambda row: row["criterion_score_mean"], reverse=True)


def _criterion_score(verifier_score: float, text: str, weights: dict[str, Any]) -> float:
    metrics = compute_text_metrics(text)
    style_defects = (
        metrics["abnormal_symbol_count"]
        + metrics["code_fence_mismatch"]
        + metrics["slogan_phrase_count"]
    )
    return (
        float(verifier_score)
        - float(weights["repeated_penalty"]) * float(metrics["repeated_line_count"])
        - float(weights["length_penalty_per_100_words"]) * float(metrics["word_count"]) / 100.0
        - float(weights["abnormal_penalty"]) * float(style_defects)
    )


def _load_or_score_validation(
    *,
    val_rows: list[dict[str, Any]],
    cache_path: Path,
    endpoint: str,
) -> list[dict[str, Any]]:
    if cache_path.exists():
        cached = _read_jsonl(cache_path)
        if len(cached) >= len(val_rows):
            return cached[: len(val_rows)]

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    client = HTTPVerifierClient(
        endpoint=endpoint,
        api_key=os.environ.get("MODEL_API_KEY", ""),
        timeout_seconds=60,
    )
    scored = []
    started = time.time()
    for index, row in enumerate(val_rows, start=1):
        prompt = str(row.get("instruction", row.get("input", "")))
        chosen = str(row["chosen"])
        rejected = str(row["rejected"])
        scored.append(
            {
                "index": index,
                "prompt_id": row.get("metadata", {}).get("prompt_id", f"val-{index:04d}"),
                "prompt": prompt,
                "chosen_text": chosen,
                "rejected_text": rejected,
                "chosen_score": client.score(prompt, chosen),
                "rejected_score": client.score(prompt, rejected),
            }
        )
        if index % 50 == 0:
            print(f"[criteria] scored validation pairs {index}/{len(val_rows)}", flush=True)
    _write_jsonl(cache_path, scored)
    print(f"[criteria] validation scoring runtime_seconds={time.time() - started:.3f}", flush=True)
    return scored


def _render_report(
    *,
    val_pairs: int,
    criteria_rows: list[dict[str, Any]],
    chosen_criteria: dict[str, Any],
    method_rows: list[dict[str, Any]],
    args: argparse.Namespace,
    criteria_csv: Path,
    method_csv: Path,
) -> str:
    return "\n".join(
        [
            "# P21 TTC 判断标准搜索报告",
            "",
            f"- created_at: `{datetime.now(timezone.utc).isoformat()}`",
            f"- val_rm: `{args.val_rm}`",
            f"- validation_pairs: `{val_pairs}`",
            f"- merged_output: `{args.merged_output}`",
            f"- output_scores: `{args.score_jsonl}`",
            f"- criteria_grid: `{criteria_csv}`",
            f"- method_scores: `{method_csv}`",
            "",
            "## 测试方式与合理性",
            "",
            "本测试先在 RM 验证集上搜索评价标准。每个标准都必须把人工构造的 chosen 答案排在 rejected 答案前面，之后才用于比较 raw、SFT、P15 TTC 和 P19 TTC。这样做的目的，是避免事后选择只对 TTC 有利、但不能识别真实坏答案的指标。",
            "",
            "候选标准以 verifier reward 为主项，并加入可解释的缺陷惩罚：重复行、答案长度、异常符号/代码块不匹配/空洞短语。搜索不会重新生成答案，不修改模型权重，也不改测试集。",
            "",
            "## 选定标准",
            "",
            "```json",
            json.dumps(chosen_criteria, ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
            "选定逻辑：先保留验证集 pairwise accuracy 接近最优的标准，再选择 mean_margin 最大的一个；若 mean_margin 接近，再选择惩罚更轻的标准。这样可以避免选择虽然准确但区分度较弱的标准。",
            "",
            "## 验证集前 10 个标准",
            "",
            _markdown_table(criteria_rows[:10]),
            "",
            "## 四组输出排序",
            "",
            _markdown_table(method_rows),
            "",
            "## 结论",
            "",
            "合适的判断标准不应是单一静态格式分，也不应只看未校准的 verifier reward。当前更合理的主质量标准是“标签校准后的 verifier reward 加异常符号/格式噪声惩罚”。重复行和长度不应直接并入主质量分，因为验证集标签没有显示它们能稳定区分 chosen/rejected；它们更适合作为解码副作用 guardrail 单独报告。",
            "",
        ]
    )


def _markdown_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    keys = list(rows[0].keys())
    lines = [
        "| " + " | ".join(keys) + " |",
        "| " + " | ".join("---" for _ in keys) + " |",
    ]
    for row in rows:
        cells = []
        for key in keys:
            value = row.get(key, "")
            cells.append(f"{value:.4f}" if isinstance(value, float) else str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _read_output_scores(path: Path) -> dict[str, dict[str, float]]:
    scores: dict[str, dict[str, float]] = defaultdict(dict)
    for row in _read_jsonl(path):
        scores[str(row["prompt_id"])][str(row["method"])] = float(row["score"])
    return scores


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


if __name__ == "__main__":
    raise SystemExit(main())
