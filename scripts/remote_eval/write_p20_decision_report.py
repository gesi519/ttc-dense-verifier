from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a Chinese decision report for the four-way P20 evaluation.")
    parser.add_argument("--metrics-csv", required=True)
    parser.add_argument("--score-summary", required=True)
    parser.add_argument("--score-jsonl", required=True)
    parser.add_argument("--merged-jsonl", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--failure-sample-output", required=True)
    args = parser.parse_args()

    metrics = _read_csv(Path(args.metrics_csv))
    score_summary = _read_json(Path(args.score_summary))
    score_rows = _read_jsonl(Path(args.score_jsonl))
    merged_rows = _read_jsonl(Path(args.merged_jsonl))

    output_path = Path(args.output)
    failure_path = Path(args.failure_sample_output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    failure_path.parent.mkdir(parents=True, exist_ok=True)

    failure_samples = _build_failure_samples(score_rows, merged_rows)
    failure_path.write_text(_render_failure_samples(failure_samples), encoding="utf-8")
    output_path.write_text(_render_report(metrics, score_summary, args, failure_path), encoding="utf-8")
    print(json.dumps({"output": str(output_path), "failure_sample_output": str(failure_path)}, ensure_ascii=False, indent=2))
    return 0


def _build_failure_samples(score_rows: list[dict[str, Any]], merged_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scores: dict[str, dict[str, float]] = defaultdict(dict)
    answers: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in score_rows:
        scores[str(row["prompt_id"])][str(row["method"])] = float(row["score"])
    for row in merged_rows:
        answers[str(row["prompt_id"])][str(row["method"])] = row

    losses = []
    for prompt_id, method_scores in scores.items():
        if "ttc_penalty" not in method_scores or "ttc_beam" not in method_scores:
            continue
        margin = method_scores["ttc_penalty"] - method_scores["ttc_beam"]
        if margin < 0:
            losses.append((margin, prompt_id))
    losses.sort()

    samples = []
    for margin, prompt_id in losses[:12]:
        samples.append(
            {
                "prompt_id": prompt_id,
                "margin_vs_ttc_beam": margin,
                "scores": scores[prompt_id],
                "prompt": answers[prompt_id].get("ttc_penalty", {}).get("prompt", ""),
                "ttc_beam_answer": answers[prompt_id].get("ttc_beam", {}).get("final_answer", ""),
                "ttc_penalty_answer": answers[prompt_id].get("ttc_penalty", {}).get("final_answer", ""),
            }
        )
    return samples


def _render_report(metrics: list[dict[str, str]], score_summary: dict[str, Any], args: argparse.Namespace, failure_path: Path) -> str:
    by_method = {row["method"]: row for row in metrics}
    mean = score_summary["mean"]
    median = score_summary["median"]
    pairwise = score_summary["pairwise"]
    p15_repeated = float(by_method["ttc_beam"]["repeated_line_count_total"])
    p19_repeated = float(by_method["ttc_penalty"]["repeated_line_count_total"])
    p15_words = float(by_method["ttc_beam"]["word_count_mean"])
    p19_words = float(by_method["ttc_penalty"]["word_count_mean"])
    repeated_drop = (p15_repeated - p19_repeated) / p15_repeated
    verifier_drop = float(mean["ttc_beam"]) - float(mean["ttc_penalty"])

    lines = [
        "# P20 四组统一评测决策报告",
        "",
        f"- created_at: `{datetime.now(timezone.utc).isoformat()}`",
        f"- metrics_csv: `{args.metrics_csv}`",
        f"- score_summary: `{args.score_summary}`",
        f"- failure_samples: `{failure_path}`",
        "",
        "## 测试方式与合理性",
        "",
        "本报告读取 P20 四组统一评测的脚本产物，不重新生成答案，也不修改任何模型权重。四组输出来自同一 500 条测试提示，合并脚本已确认每组 500 条、无缺失、无重复、无空答案。静态指标用于检查 P15 暴露的重复和冗长问题，verifier 全量评分用于检查 P19 惩罚项是否破坏原有 verifier 偏好收益。",
        "",
        "这种测试合理，因为 P19 的实验变量只在解码期 rerank score 中加入长度和重复行惩罚。若重复降低但 verifier 分数明显下降，说明惩罚过强或目标函数需要调参，而不能直接宣称 P19 优于 P15。",
        "",
        "## 主要指标",
        "",
        "| method | verifier_mean | verifier_median | repeated_line_total | word_count_mean | latency_ms_mean | verifier_call_count_mean |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for method in ["raw_32b", "sft_32b", "ttc_beam", "ttc_penalty"]:
        row = by_method[method]
        lines.append(
            "| {method} | {mean:.4f} | {median:.4f} | {repeat} | {words} | {latency} | {calls} |".format(
                method=method,
                mean=float(mean[method]),
                median=float(median[method]),
                repeat=row["repeated_line_count_total"],
                words=row["word_count_mean"],
                latency=row["latency_ms_mean"],
                calls=row["verifier_call_count_mean"],
            )
        )

    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"P19 相对 P15 将 repeated_line_total 从 {int(p15_repeated)} 降到 {int(p19_repeated)}，下降约 {repeated_drop:.1%}；word_count_mean 从 {p15_words:.3f} 降到 {p19_words:.3f}。这说明长度和重复惩罚确实缓解了 P15 的可见重复问题。",
            "",
            f"代价是 verifier mean 从 {float(mean['ttc_beam']):.4f} 降到 {float(mean['ttc_penalty']):.4f}，下降 {verifier_drop:.4f}。P19 相对 P15 只赢 {pairwise['ttc_penalty_beats_ttc_beam']}/500，输 {pairwise['ttc_penalty_loses_ttc_beam']}/500。因此 P19 不能作为最终优于 P15 的结论，只能作为证明“解码期正则化有效但当前惩罚过强”的诊断实验。",
            "",
            f"相对 raw/SFT，P19 仍分别赢 {pairwise['ttc_penalty_beats_raw_32b']}/500 和 {pairwise['ttc_penalty_beats_sft_32b']}/500，说明 TTC 主线并未失败；失败点在 P19 与 P15 之间的质量-简洁性权衡。",
            "",
            "## 下一步建议",
            "",
            "不建议直接清理并进入最终论文报告。下一轮应运行较轻惩罚的 P21：保留 repeated_line_penalty=0.5，将 length_penalty_per_100_words 从 0.15 降到 0.05，或同时增加一个只惩罚重复行、不惩罚长度的消融。预期影响是重新调用 32B generator 和 7B verifier，500 条约 4 小时，不改模型权重、不写 checkpoint，只新增 outputs/ttc、runs/ttc 和 reports/eval 下的本项目产物。",
            "",
        ]
    )
    return "\n".join(lines)


def _render_failure_samples(samples: list[dict[str, Any]]) -> str:
    lines = [
        "# P20 P19 相对 P15 劣化样本抽样",
        "",
        "这些样本按 `ttc_penalty_score - ttc_beam_score` 从低到高排序，用于人工检查惩罚项是否过度压低了有价值的详细解释。",
        "",
    ]
    for sample in samples:
        lines.extend(
            [
                f"## {sample['prompt_id']}",
                "",
                f"- margin_vs_ttc_beam: `{sample['margin_vs_ttc_beam']:.4f}`",
                f"- scores: `{json.dumps(sample['scores'], ensure_ascii=False, sort_keys=True)}`",
                "",
                "### Prompt",
                "",
                _truncate(sample["prompt"], 1000),
                "",
                "### P15 TTC Beam",
                "",
                _truncate(sample["ttc_beam_answer"], 1800),
                "",
                "### P19 TTC Penalty",
                "",
                _truncate(sample["ttc_penalty_answer"], 1800),
                "",
            ]
        )
    return "\n".join(lines)


def _truncate(text: str, limit: int) -> str:
    text = str(text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 20].rstrip() + "\n\n...[truncated]..."


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


if __name__ == "__main__":
    raise SystemExit(main())
