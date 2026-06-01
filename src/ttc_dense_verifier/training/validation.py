from __future__ import annotations

import math
from statistics import mean
from typing import Any

from ttc_dense_verifier.evaluation.metrics import compute_text_metrics


def validate_verifier_scores(
    rows: list[dict[str, Any]],
    *,
    min_pairwise_accuracy: float = 0.65,
) -> dict[str, Any]:
    if not rows:
        return {
            "count": 0,
            "pairwise_accuracy": 0.0,
            "passed_min_accuracy": False,
            "mean_margin": 0.0,
            "median_margin": 0.0,
            "length_score_correlation": 0.0,
            "markdown_score_correlation": 0.0,
            "failures": [],
        }

    margins: list[float] = []
    chosen_scores: list[float] = []
    rejected_scores: list[float] = []
    length_deltas: list[float] = []
    markdown_deltas: list[float] = []
    failures: list[dict[str, Any]] = []

    for row in rows:
        chosen_score = float(row["chosen_score"])
        rejected_score = float(row["rejected_score"])
        margin = chosen_score - rejected_score
        margins.append(margin)
        chosen_scores.append(chosen_score)
        rejected_scores.append(rejected_score)
        if margin <= 0:
            failures.append(
                {
                    "prompt_id": row.get("prompt_id"),
                    "chosen_score": chosen_score,
                    "rejected_score": rejected_score,
                    "margin": margin,
                }
            )

        chosen_metrics = compute_text_metrics(str(row.get("chosen", "")))
        rejected_metrics = compute_text_metrics(str(row.get("rejected", "")))
        length_deltas.append(float(chosen_metrics["word_count"]) - float(rejected_metrics["word_count"]))
        markdown_deltas.append(float(chosen_metrics["heading_count"]) - float(rejected_metrics["heading_count"]))

    pairwise_accuracy = sum(1 for margin in margins if margin > 0) / len(margins)
    return {
        "count": len(rows),
        "pairwise_accuracy": pairwise_accuracy,
        "passed_min_accuracy": pairwise_accuracy >= min_pairwise_accuracy,
        "mean_margin": mean(margins),
        "median_margin": _median(margins),
        "min_margin": min(margins),
        "max_margin": max(margins),
        "length_score_correlation": _pearson(length_deltas, margins),
        "markdown_score_correlation": _pearson(markdown_deltas, margins),
        "failures": failures,
    }


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2


def _pearson(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        return 0.0
    left_mean = mean(left)
    right_mean = mean(right)
    numerator = sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right))
    left_denominator = math.sqrt(sum((x - left_mean) ** 2 for x in left))
    right_denominator = math.sqrt(sum((y - right_mean) ** 2 for y in right))
    denominator = left_denominator * right_denominator
    if denominator == 0:
        return 0.0
    return numerator / denominator
