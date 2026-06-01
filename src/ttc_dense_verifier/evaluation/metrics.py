from __future__ import annotations

import re
from collections import defaultdict
from numbers import Number
from typing import Any

ABNORMAL_SYMBOL_PATTERNS = [
    re.compile(r">>>+"),
    re.compile(r"===>+"),
    re.compile(r"-{2,}>"),
    re.compile(r"<-{2,}"),
    re.compile(r"={3,}"),
]

SLOGAN_PHRASES = [
    "game changer",
    "revolutionary",
    "next level",
    "breakthrough",
    "unlock the power",
    "slogan",
]


def compute_text_metrics(text: str) -> dict[str, int | float]:
    lines = text.splitlines()
    abnormal_symbol_count = sum(len(pattern.findall(text)) for pattern in ABNORMAL_SYMBOL_PATTERNS)
    slogan_phrase_count = sum(text.lower().count(phrase) for phrase in SLOGAN_PHRASES)
    heading_count = sum(1 for line in lines if re.match(r"^#{1,6}\s+\S", line))
    list_item_count = sum(1 for line in lines if re.match(r"^\s*(?:[-*+]|\d+[.)])\s+\S", line))
    code_fence_mismatch = text.count("```") % 2
    word_count = len(re.findall(r"[A-Za-z0-9_]+", text))
    repeated_line_count = _count_repeated_nonempty_lines(lines)
    return {
        "abnormal_symbol_count": abnormal_symbol_count,
        "code_fence_mismatch": code_fence_mismatch,
        "slogan_phrase_count": slogan_phrase_count,
        "heading_count": heading_count,
        "list_item_count": list_item_count,
        "character_count": len(text),
        "word_count": word_count,
        "repeated_line_count": repeated_line_count,
    }


def _count_repeated_nonempty_lines(lines: list[str]) -> int:
    seen: set[str] = set()
    repeated = 0
    for line in lines:
        normalized = line.strip().lower()
        if not normalized:
            continue
        if normalized in seen:
            repeated += 1
        seen.add(normalized)
    return repeated


def summarize_metrics(rows: list[dict[str, Any]]) -> dict[str, dict[str, int | float]]:
    grouped: dict[str, list[dict[str, Number]]] = defaultdict(list)
    for row in rows:
        method = str(row.get("method", "unknown"))
        metrics = row.get("metrics", {})
        numeric_metrics = {key: value for key, value in metrics.items() if isinstance(value, Number)}
        grouped[method].append(numeric_metrics)

    summary: dict[str, dict[str, int | float]] = {}
    for method, metric_rows in grouped.items():
        method_summary: dict[str, int | float] = {"count": len(metric_rows)}
        metric_names = sorted({key for metrics in metric_rows for key in metrics})
        for name in metric_names:
            values = [metrics[name] for metrics in metric_rows if name in metrics]
            method_summary[f"{name}_mean"] = sum(values) / len(values) if values else 0
        summary[method] = method_summary
    return summary
