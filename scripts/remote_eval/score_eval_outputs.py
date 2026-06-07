from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ttc_dense_verifier.serving.clients import HTTPVerifierClient


def main() -> int:
    parser = argparse.ArgumentParser(description="Score merged evaluation outputs with the verifier service.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config)
    cfg = _read_json(config_path)
    paths = cfg["paths"]
    merged_path = Path(paths["merged_output"])
    score_path = Path(paths["score_output"])
    summary_path = Path(paths["summary_json"])
    score_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    rows = _read_jsonl(merged_path)
    report_base = {
        "run_id": cfg["run_id"],
        "config_path": str(config_path),
        "merged_output": str(merged_path),
        "score_output": str(score_path),
        "summary_json": str(summary_path),
        "verifier_endpoint": cfg["verifier_endpoint"],
        "verifier_model": cfg.get("verifier_model", ""),
        "row_count": len(rows),
        "dry_run": bool(args.dry_run),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
    }
    if args.dry_run:
        print(json.dumps(report_base, ensure_ascii=False, indent=2))
        _write_json(summary_path, report_base)
        return 0

    client = HTTPVerifierClient(
        endpoint=str(cfg["verifier_endpoint"]),
        api_key=os.environ.get("MODEL_API_KEY") or str(cfg.get("api_key", "")),
        timeout_seconds=float(cfg.get("timeout_seconds", 60)),
    )

    started = time.time()
    scored_rows: list[dict[str, Any]] = []
    for row in rows:
        score = client.score(str(row.get("prompt", "")), str(row.get("final_answer", "")))
        scored = {
            "prompt_id": row.get("prompt_id"),
            "method": row.get("method"),
            "score": score,
            "source_run_id": row.get("source_run_id", ""),
        }
        scored_rows.append(scored)

    _write_jsonl(score_path, scored_rows)
    summary = {
        **report_base,
        "runtime_seconds": time.time() - started,
        **_summarize_scores(scored_rows, cfg.get("comparisons", {})),
    }
    _write_json(summary_path, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def _summarize_scores(rows: list[dict[str, Any]], comparisons: dict[str, Any]) -> dict[str, Any]:
    by_method: dict[str, list[float]] = defaultdict(list)
    by_prompt: dict[str, dict[str, float]] = defaultdict(dict)
    for row in rows:
        method = str(row.get("method", "unknown"))
        prompt_id = str(row.get("prompt_id", ""))
        score = float(row.get("score", 0.0))
        by_method[method].append(score)
        by_prompt[prompt_id][method] = score

    candidate = str(comparisons.get("candidate_method", ""))
    references = [str(item) for item in comparisons.get("reference_methods", [])]
    pairwise: dict[str, Any] = {}
    if candidate:
        for reference in references:
            wins = []
            losses = []
            ties = []
            for prompt_id, scores in by_prompt.items():
                if candidate not in scores or reference not in scores:
                    continue
                if scores[candidate] > scores[reference]:
                    wins.append(prompt_id)
                elif scores[candidate] < scores[reference]:
                    losses.append(prompt_id)
                else:
                    ties.append(prompt_id)
            pairwise[f"{candidate}_beats_{reference}"] = len(wins)
            pairwise[f"{candidate}_loses_{reference}"] = len(losses)
            pairwise[f"{candidate}_ties_{reference}"] = len(ties)
            pairwise[f"{candidate}_loses_{reference}_ids"] = losses[:50]

    return {
        "score_count": {method: len(values) for method, values in sorted(by_method.items())},
        "mean": {method: statistics.mean(values) for method, values in sorted(by_method.items()) if values},
        "median": {method: statistics.median(values) for method, values in sorted(by_method.items()) if values},
        "min": {method: min(values) for method, values in sorted(by_method.items()) if values},
        "max": {method: max(values) for method, values in sorted(by_method.items()) if values},
        "pairwise": pairwise,
    }


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


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _git_commit() -> str:
    if not Path(".git/HEAD").exists():
        return "not-a-git-checkout"
    return os.popen("git rev-parse HEAD 2>/dev/null").read().strip() or "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
