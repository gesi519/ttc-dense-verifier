from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge raw, SFT, and TTC outputs into one evaluation JSONL.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    cfg_path = Path(args.config)
    cfg = _read_json(cfg_path)
    paths = cfg["paths"]
    output_path = Path(paths["merged_output"])
    report_path = Path(paths["report_json"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    prompts = _read_jsonl(Path(paths["test_prompts"]))
    expected_ids = [str(row["prompt_id"]) for row in prompts]
    expected_set = set(expected_ids)
    method_specs = cfg["methods"]

    report: dict[str, Any] = {
        "run_id": cfg["run_id"],
        "config_path": str(cfg_path),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
        "expected_count": len(expected_ids),
        "methods": {},
        "dry_run": bool(args.dry_run),
    }
    merged: list[dict[str, Any]] = []
    ok = True

    for method, spec in method_specs.items():
        rows = _read_jsonl(Path(spec["path"]))
        answer_key = str(spec["answer_key"])
        normalized = []
        row_ids = [str(row.get("prompt_id", "")) for row in rows]
        missing = sorted(expected_set - set(row_ids))
        extra = sorted(set(row_ids) - expected_set)
        duplicates = sorted({prompt_id for prompt_id in row_ids if row_ids.count(prompt_id) > 1})
        empty = [str(row.get("prompt_id", "")) for row in rows if not str(row.get(answer_key, "")).strip()]
        method_ok = len(rows) == len(expected_ids) and not missing and not extra and not duplicates and not empty
        ok = ok and method_ok
        report["methods"][method] = {
            "path": spec["path"],
            "rows": len(rows),
            "answer_key": answer_key,
            "missing_count": len(missing),
            "extra_count": len(extra),
            "duplicate_count": len(duplicates),
            "empty_count": len(empty),
            "missing": missing[:20],
            "extra": extra[:20],
            "duplicates": duplicates[:20],
            "empty": empty[:20],
            "ok": method_ok,
        }
        for row in rows:
            normalized.append(
                {
                    "prompt_id": row.get("prompt_id"),
                    "prompt": row.get("prompt", ""),
                    "method": method,
                    "final_answer": row.get(answer_key, ""),
                    "latency_ms": row.get("latency_ms", 0),
                    "verifier_call_count": row.get("verifier_call_count", 0),
                    "source_model": row.get("model", row.get("generator_model", "")),
                    "source_run_id": row.get("run_id", ""),
                }
            )
        normalized_by_id = {str(row["prompt_id"]): row for row in normalized}
        merged.extend(normalized_by_id[prompt_id] for prompt_id in expected_ids if prompt_id in normalized_by_id)

    report["merged_rows"] = len(merged)
    report["ok"] = ok and len(merged) == len(expected_ids) * len(method_specs)
    if not args.dry_run:
        _write_jsonl(output_path, merged)
    _write_json(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


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

