from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt


METHOD_LABELS = {
    "raw_32b": "Raw 32B",
    "sft_32b": "SFT 32B",
    "ttc_beam": "P15 TTC",
    "ttc_penalty": "P19 TTC Penalty",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Export final Chinese LaTeX paper-style evaluation report.")
    parser.add_argument("--metrics-csv", required=True)
    parser.add_argument("--score-summary", required=True)
    parser.add_argument("--criteria-method-csv", required=True)
    parser.add_argument("--criteria-report", required=True)
    parser.add_argument("--decision-report", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    figures_dir = output_dir / "figures"
    tables_dir = output_dir / "tables"
    output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)

    metrics = _read_csv(Path(args.metrics_csv))
    method_scores = _read_csv(Path(args.criteria_method_csv))
    score_summary = _read_json(Path(args.score_summary))

    _write_main_table(tables_dir / "main_results_table.csv", metrics, method_scores, score_summary)
    _plot_quality(figures_dir / "fig_quality_mean.png", figures_dir / "fig_quality_mean.pdf", method_scores)
    _plot_pairwise(figures_dir / "fig_pairwise_win_rate.png", figures_dir / "fig_pairwise_win_rate.pdf", score_summary)
    _plot_side_effects(figures_dir / "fig_repetition_length.png", figures_dir / "fig_repetition_length.pdf", metrics)
    _plot_pareto(figures_dir / "fig_pareto_quality_repetition.png", figures_dir / "fig_pareto_quality_repetition.pdf", method_scores)
    _write_plot_manifest(output_dir / "figure_manifest.json", figures_dir)

    tex_path = output_dir / "ttc_dense_verifier_final_report_zh.tex"
    tex_path.write_text(
        _render_latex(
            metrics=metrics,
            method_scores=method_scores,
            score_summary=score_summary,
            criteria_report=args.criteria_report,
            decision_report=args.decision_report,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"tex": str(tex_path), "figures_dir": str(figures_dir), "tables_dir": str(tables_dir)}, ensure_ascii=False, indent=2))
    return 0


def _write_main_table(path: Path, metrics: list[dict[str, str]], method_scores: list[dict[str, str]], summary: dict[str, Any]) -> None:
    by_metric = {row["method"]: row for row in metrics}
    by_score = {row["method"]: row for row in method_scores}
    rows = []
    for method in ["raw_32b", "sft_32b", "ttc_beam", "ttc_penalty"]:
        rows.append(
            {
                "method": method,
                "quality_mean": by_score[method]["criterion_score_mean"],
                "quality_median": by_score[method]["criterion_score_median"],
                "verifier_mean": summary["mean"][method],
                "repeated_line_total": by_metric[method]["repeated_line_count_total"],
                "word_count_mean": by_metric[method]["word_count_mean"],
                "latency_ms_mean": by_metric[method]["latency_ms_mean"],
                "verifier_call_count_mean": by_metric[method]["verifier_call_count_mean"],
            }
        )
    _write_csv(path, rows)


def _plot_quality(png_path: Path, pdf_path: Path, rows: list[dict[str, str]]) -> None:
    methods = ["raw_32b", "sft_32b", "ttc_beam", "ttc_penalty"]
    values = [_float(_row(rows, method)["criterion_score_mean"]) for method in methods]
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar([METHOD_LABELS[m] for m in methods], values, color=["#667085", "#7A5C58", "#2E7D6B", "#B85C38"])
    ax.axhline(0, color="#222222", linewidth=0.8)
    ax.set_ylabel("Calibrated quality score")
    ax.set_title("Main quality comparison")
    ax.bar_label(bars, fmt="%.2f", padding=3)
    fig.tight_layout()
    fig.savefig(png_path, dpi=180)
    fig.savefig(pdf_path)
    plt.close(fig)


def _plot_pairwise(png_path: Path, pdf_path: Path, summary: dict[str, Any]) -> None:
    pairs = [
        ("P15 vs Raw", 432 / 500),
        ("P15 vs SFT", 434 / 500),
        ("P19 vs Raw", summary["pairwise"]["ttc_penalty_beats_raw_32b"] / 500),
        ("P19 vs SFT", summary["pairwise"]["ttc_penalty_beats_sft_32b"] / 500),
        ("P19 vs P15", summary["pairwise"]["ttc_penalty_beats_ttc_beam"] / 500),
    ]
    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar([item[0] for item in pairs], [item[1] for item in pairs], color="#3D6B99")
    ax.axhline(0.5, color="#333333", linestyle="--", linewidth=1)
    ax.set_ylim(0, 1)
    ax.set_ylabel("Pairwise win rate")
    ax.set_title("Pairwise preference under verifier scoring")
    ax.bar_label(bars, labels=[f"{value:.1%}" for _, value in pairs], padding=3)
    fig.autofmt_xdate(rotation=18)
    fig.tight_layout()
    fig.savefig(png_path, dpi=180)
    fig.savefig(pdf_path)
    plt.close(fig)


def _plot_side_effects(png_path: Path, pdf_path: Path, rows: list[dict[str, str]]) -> None:
    methods = ["raw_32b", "sft_32b", "ttc_beam", "ttc_penalty"]
    repeated = [_float(_row(rows, method)["repeated_line_count_total"]) for method in methods]
    words = [_float(_row(rows, method)["word_count_mean"]) for method in methods]
    fig, ax1 = plt.subplots(figsize=(8, 4))
    x = range(len(methods))
    bars = ax1.bar([i - 0.18 for i in x], repeated, width=0.36, label="Repeated lines", color="#9A4D4D")
    ax2 = ax1.twinx()
    ax2.plot([i + 0.18 for i in x], words, marker="o", label="Mean words", color="#2E6F9E")
    ax1.set_xticks(list(x), [METHOD_LABELS[m] for m in methods])
    ax1.set_ylabel("Repeated line total")
    ax2.set_ylabel("Mean word count")
    ax1.set_title("Side-effect guardrails")
    ax1.bar_label(bars, fmt="%.0f", padding=3)
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right")
    fig.tight_layout()
    fig.savefig(png_path, dpi=180)
    fig.savefig(pdf_path)
    plt.close(fig)


def _plot_pareto(png_path: Path, pdf_path: Path, rows: list[dict[str, str]]) -> None:
    methods = ["raw_32b", "sft_32b", "ttc_beam", "ttc_penalty"]
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    for method in methods:
        row = _row(rows, method)
        x = _float(row["repeated_line_total"])
        y = _float(row["criterion_score_mean"])
        ax.scatter(x, y, s=80)
        ax.annotate(METHOD_LABELS[method], (x, y), xytext=(7, 5), textcoords="offset points")
    ax.set_xlabel("Repeated line total")
    ax.set_ylabel("Calibrated quality score")
    ax.set_title("Quality and repetition trade-off")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(png_path, dpi=180)
    fig.savefig(pdf_path)
    plt.close(fig)


def _write_plot_manifest(path: Path, figures_dir: Path) -> None:
    files = sorted(str(item.relative_to(path.parent)) for item in figures_dir.iterdir() if item.is_file())
    path.write_text(json.dumps({"created_at": datetime.now(timezone.utc).isoformat(), "files": files}, indent=2), encoding="utf-8")


def _render_latex(
    *,
    metrics: list[dict[str, str]],
    method_scores: list[dict[str, str]],
    score_summary: dict[str, Any],
    criteria_report: str,
    decision_report: str,
) -> str:
    m = {row["method"]: row for row in metrics}
    s = {row["method"]: row for row in method_scores}
    pairwise = score_summary["pairwise"]
    p15_quality = _float(s["ttc_beam"]["criterion_score_mean"])
    p19_quality = _float(s["ttc_penalty"]["criterion_score_mean"])
    raw_quality = _float(s["raw_32b"]["criterion_score_mean"])
    sft_quality = _float(s["sft_32b"]["criterion_score_mean"])
    p15_repeat = int(_float(m["ttc_beam"]["repeated_line_count_total"]))
    p19_repeat = int(_float(m["ttc_penalty"]["repeated_line_count_total"]))
    raw_repeat = int(_float(m["raw_32b"]["repeated_line_count_total"]))
    sft_repeat = int(_float(m["sft_32b"]["repeated_line_count_total"]))
    p19_repeat_drop = (p15_repeat - p19_repeat) / p15_repeat

    return rf"""\documentclass[UTF8]{{ctexart}}
\usepackage[a4paper,margin=2.2cm]{{geometry}}
\usepackage{{booktabs}}
\usepackage{{graphicx}}
\usepackage{{hyperref}}
\usepackage{{amsmath}}
\usepackage{{float}}
\usepackage{{caption}}
\hypersetup{{colorlinks=true,linkcolor=black,urlcolor=blue}}

\title{{TTC Dense Verifier 评测报告}}
\author{{自动实验报告}}
\date{{{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}}}

\begin{{document}}
\maketitle

\begin{{abstract}}
本报告评估面向代码与系统编程问答的 TTC Dense Verifier 工作流。实验比较冻结 Qwen2.5-32B 原始生成、Qwen2.5-32B LoRA SFT、P15 TTC beam rerank 和 P19 带副作用惩罚的 TTC rerank。结论是：P15 在校准主质量分上最强，适合作为证明 TTC 提升回答质量的主结果；P19 显著降低重复行，适合作为解码期副作用控制消融。
\end{{abstract}}

\section{{实验设置}}
生成模型为冻结的 Qwen2.5-32B-Instruct。验证器为 Qwen2.5-7B-RM-P10MULTI\_20260604\_055439 的 checkpoint-600。测试集为 \texttt{{data/preference/test\_prompts.jsonl}} 中的 500 条代码与系统编程问题。四组输出均使用同一测试集，且完整性检查确认每组 500 条、无缺失、无重复、无空答案。

\section{{评测标准}}
P21 标准搜索先在 500 对 RM 验证集 chosen/rejected 上校准指标，再应用到四组输出。主质量分定义为：
\[
quality = verifier\_reward - 2.0 \times style\_noise
\]
其中：
\[
style\_noise = abnormal\_symbol + code\_fence\_mismatch + slogan\_phrase
\]
该标准在验证集上的 pairwise accuracy 为 1.0，mean margin 为 33.2985，min margin 为 8.1796。重复行、平均长度和延迟不并入主质量分，而作为副作用 guardrail 单独报告，避免把较详细的技术解释误判为低质量。

\section{{主结果}}
\begin{{table}}[H]
\centering
\caption{{四组方法主指标}}
\begin{{tabular}}{{lrrrrr}}
\toprule
方法 & 主质量均值 & 主质量中位数 & 重复行总数 & 平均词数 & 平均延迟 ms \\
\midrule
Raw 32B & {raw_quality:.4f} & {_float(s['raw_32b']['criterion_score_median']):.4f} & {raw_repeat} & {_float(m['raw_32b']['word_count_mean']):.3f} & {_float(m['raw_32b']['latency_ms_mean']):.1f} \\
SFT 32B & {sft_quality:.4f} & {_float(s['sft_32b']['criterion_score_median']):.4f} & {sft_repeat} & {_float(m['sft_32b']['word_count_mean']):.3f} & {_float(m['sft_32b']['latency_ms_mean']):.1f} \\
P15 TTC & {p15_quality:.4f} & {_float(s['ttc_beam']['criterion_score_median']):.4f} & {p15_repeat} & {_float(m['ttc_beam']['word_count_mean']):.3f} & {_float(m['ttc_beam']['latency_ms_mean']):.1f} \\
P19 TTC Penalty & {p19_quality:.4f} & {_float(s['ttc_penalty']['criterion_score_median']):.4f} & {p19_repeat} & {_float(m['ttc_penalty']['word_count_mean']):.3f} & {_float(m['ttc_penalty']['latency_ms_mean']):.1f} \\
\bottomrule
\end{{tabular}}
\end{{table}}

P15 的主质量均值为 {p15_quality:.4f}，显著高于 Raw 32B 的 {raw_quality:.4f} 和 SFT 32B 的 {sft_quality:.4f}。P15 相对 Raw 和 SFT 的 pairwise 胜率分别为 432/500 和 434/500。因此，P15 是证明 TTC 提升任务回答质量的最佳主结果。

\begin{{figure}}[H]
\centering
\includegraphics[width=0.82\linewidth]{{figures/fig_quality_mean.png}}
\caption{{校准主质量分对比。}}
\end{{figure}}

\begin{{figure}}[H]
\centering
\includegraphics[width=0.9\linewidth]{{figures/fig_pairwise_win_rate.png}}
\caption{{相对 baseline 与 TTC 变体的 pairwise 胜率。}}
\end{{figure}}

\section{{副作用分析}}
P15 的重复行总数为 {p15_repeat}，高于 Raw 32B 的 {raw_repeat} 和 SFT 32B 的 {sft_repeat}。P19 将重复行总数降到 {p19_repeat}，相对 P15 下降 {p19_repeat_drop:.1%}，但主质量均值从 {p15_quality:.4f} 降到 {p19_quality:.4f}。这说明副作用惩罚有效，但当前惩罚强度牺牲了部分技术质量。

\begin{{figure}}[H]
\centering
\includegraphics[width=0.9\linewidth]{{figures/fig_repetition_length.png}}
\caption{{重复行和平均长度的副作用指标。}}
\end{{figure}}

\begin{{figure}}[H]
\centering
\includegraphics[width=0.78\linewidth]{{figures/fig_pareto_quality_repetition.png}}
\caption{{主质量与重复行之间的 Pareto 权衡。}}
\end{{figure}}

\section{{结论}}
按当前证据，P15 TTC beam 是更好的主方法：它在校准主质量分和 pairwise 胜率上均优于 P19，并显著优于 Raw/SFT baseline。P19 不应作为主结果，但应作为重要消融保留，因为它证明解码期目标可以控制 TTC 的重复副作用。

最终叙事应为：TTC 通过 7B verifier 在解码期重排 32B generator 的候选答案，提升了代码与系统编程问答的技术质量；副作用是计算成本和重复行增加；加入副作用惩罚可以降低重复，但会带来质量和简洁性的权衡。

\section{{可复现产物}}
\begin{{itemize}}
\item P20 决策报告：\texttt{{{_latex_escape(decision_report)}}}
\item P21 标准搜索报告：\texttt{{{_latex_escape(criteria_report)}}}
\item 主指标表：\texttt{{reports/paper/final\_eval/tables/main\_results\_table.csv}}
\item 图表目录：\texttt{{reports/paper/final\_eval/figures/}}
\end{{itemize}}

\end{{document}}
"""


def _row(rows: list[dict[str, str]], method: str) -> dict[str, str]:
    for row in rows:
        if row.get("method") == method:
            return row
    raise KeyError(method)


def _float(value: Any) -> float:
    return float(value)


def _latex_escape(value: str) -> str:
    return value.replace("\\", r"\textbackslash{}").replace("_", r"\_")


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
