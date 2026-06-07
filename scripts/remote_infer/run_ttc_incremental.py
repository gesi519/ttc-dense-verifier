from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ttc_dense_verifier.decoding.beam_search import BeamSearchConfig, BeamSearchTTC
from ttc_dense_verifier.inference.artifacts import build_inference_record
from ttc_dense_verifier.serving.clients import HTTPVerifierClient, OpenAICompatibleGeneratorClient


def main() -> int:
    parser = argparse.ArgumentParser(description="Run resumable TTC beam reranking inference.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config)
    cfg = _read_json(config_path)
    run_id = str(cfg["run_id"])
    paths = cfg["paths"]
    generator_cfg = cfg["generator"]
    verifier_cfg = cfg["verifier"]
    decoding_cfg = cfg["decoding"]

    prompts_path = Path(paths["input_prompts"])
    output_path = Path(paths["output_jsonl"])
    trace_path = Path(paths["trace_jsonl"])
    report_path = Path(paths["report_json"])
    for path in (output_path, trace_path, report_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    prompts = _read_jsonl(prompts_path)
    limit = cfg.get("limit")
    if limit is not None:
        prompts = prompts[: int(limit)]

    report = {
        "run_id": run_id,
        "config_path": str(config_path),
        "input_prompts": str(prompts_path),
        "output_jsonl": str(output_path),
        "trace_jsonl": str(trace_path),
        "generator_model": generator_cfg["model"],
        "generator_endpoint": generator_cfg["endpoint"],
        "verifier_model": verifier_cfg["model"],
        "verifier_endpoint": verifier_cfg["endpoint"],
        "decoding": decoding_cfg,
        "total_prompts": len(prompts),
        "dry_run": bool(args.dry_run),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(),
    }
    if args.dry_run:
        _write_json(report_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    completed = _completed_prompt_ids(output_path) if cfg.get("resume", True) else set()
    pending = [row for row in prompts if str(row["prompt_id"]) not in completed]
    print(f"[ttc] {len(pending)} pending, {len(completed)}/{len(prompts)} already written to {output_path}", flush=True)

    generator = OpenAICompatibleGeneratorClient(
        endpoint=str(generator_cfg["endpoint"]),
        model=str(generator_cfg["model"]),
        api_key=os.environ.get("MODEL_API_KEY") or str(generator_cfg.get("api_key", "")),
        timeout_seconds=float(generator_cfg.get("timeout_seconds", 180)),
        max_tokens=int(generator_cfg.get("max_tokens", 1024)),
        temperature=float(generator_cfg.get("temperature", 0.7)),
        extra_body={"top_p": float(generator_cfg.get("top_p", 0.9))},
    )
    verifier = HTTPVerifierClient(
        endpoint=str(verifier_cfg["endpoint"]),
        api_key=os.environ.get("MODEL_API_KEY") or str(verifier_cfg.get("api_key", "")),
        timeout_seconds=float(verifier_cfg.get("timeout_seconds", 60)),
    )
    decoder = BeamSearchTTC(
        generator=generator,
        verifier=verifier,
        config=BeamSearchConfig(
            beam_width=int(decoding_cfg.get("beam_width", 4)),
            expansions_per_step=int(decoding_cfg.get("expansions_per_step", 4)),
            beta=float(decoding_cfg.get("beta", 1.0)),
            max_steps=int(decoding_cfg.get("max_steps", 1)),
            length_penalty_per_100_words=float(decoding_cfg.get("length_penalty_per_100_words", 0.0)),
            repeated_line_penalty=float(decoding_cfg.get("repeated_line_penalty", 0.0)),
        ),
    )

    started = time.time()
    progress_every = int(cfg.get("progress_every", 10))
    done = len(completed)
    with output_path.open("a", encoding="utf-8", newline="\n") as output_handle, trace_path.open(
        "a", encoding="utf-8", newline="\n"
    ) as trace_handle:
        for row in pending:
            prompt_id = str(row["prompt_id"])
            prompt = str(row["prompt"])
            result = decoder.decode(prompt)
            record = build_inference_record(
                prompt_id=prompt_id,
                prompt=prompt,
                result=result,
                generator_model=str(generator_cfg["model"]),
                verifier_model=str(verifier_cfg["model"]),
            )
            record["run_id"] = run_id
            record["source_metadata"] = dict(row.get("metadata", {}))
            _append_jsonl(output_handle, record)
            _append_jsonl(
                trace_handle,
                {
                    "run_id": run_id,
                    "prompt_id": prompt_id,
                    "prompt": prompt,
                    "step_traces": record["step_traces"],
                    "branch_scores": record["branch_scores"],
                    "decoding_parameters": record["decoding_parameters"],
                },
            )
            done += 1
            if done == len(prompts) or done % progress_every == 0:
                print(f"[ttc] {done}/{len(prompts)} records written", flush=True)

    report["completed_records"] = len(_read_jsonl(output_path))
    report["runtime_seconds"] = round(time.time() - started, 3)
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


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


def _append_jsonl(handle: Any, record: dict[str, Any]) -> None:
    handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    handle.flush()


def _completed_prompt_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {str(row.get("prompt_id", "")) for row in _read_jsonl(path)}


def _git_commit() -> str:
    if not Path(".git/HEAD").exists():
        return "not-a-git-checkout"
    return os.popen("git rev-parse HEAD 2>/dev/null").read().strip() or "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
