from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def main() -> int:
    parser = argparse.ArgumentParser(description="Run raw or SFT generator baseline inference.")
    parser.add_argument("--config", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config)
    cfg = _read_json(config_path)
    run_id = str(cfg["run_id"])
    baseline = cfg["baseline"]
    infer = cfg["inference"]
    paths = cfg["paths"]

    input_path = Path(paths["input_prompts"])
    output_path = Path(paths["output_jsonl"])
    report_path = Path(paths["report_json"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    prompts = _read_jsonl(input_path)
    limit = infer.get("limit")
    if limit is not None:
        prompts = prompts[: int(limit)]

    report = {
        "run_id": run_id,
        "baseline": baseline["name"],
        "config_path": str(config_path),
        "input_prompts": str(input_path),
        "output_jsonl": str(output_path),
        "model_path": baseline["model_path"],
        "served_model_name": baseline["served_model_name"],
        "lora_path": baseline.get("lora_path"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "total_prompts": len(prompts),
        "dry_run": bool(args.dry_run),
        "git_commit": _git_commit(),
    }

    if args.dry_run:
        _write_json(report_path, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    completed = _completed_prompt_ids(output_path) if infer.get("resume", True) else set()
    pending = [row for row in prompts if str(row["prompt_id"]) not in completed]
    print(f"[baseline] {len(pending)} pending, {len(completed)}/{len(prompts)} already written to {output_path}", flush=True)

    client = OpenAIChatClient(
        endpoint=str(infer["endpoint"]).rstrip("/"),
        model=str(baseline["served_model_name"]),
        api_key=os.environ.get("MODEL_API_KEY") or str(infer.get("api_key", "")),
        timeout_seconds=float(infer.get("timeout_seconds", 120)),
        max_tokens=int(infer.get("max_tokens", 1024)),
        temperature=float(infer.get("temperature", 0.2)),
        top_p=float(infer.get("top_p", 0.9)),
    )

    started = time.time()
    with output_path.open("a", encoding="utf-8", newline="\n") as handle:
        _run_pending(
            pending,
            handle=handle,
            client=client,
            run_id=run_id,
            baseline_name=str(baseline["name"]),
            concurrency=int(infer.get("concurrency", 1)),
            max_retries=int(infer.get("max_retries", 3)),
            progress_every=int(infer.get("progress_every", 10)),
            total=len(prompts),
            already_done=len(completed),
        )

    report["completed_records"] = len(_read_jsonl(output_path))
    report["runtime_seconds"] = round(time.time() - started, 3)
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    _write_json(report_path, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


class OpenAIChatClient:
    def __init__(
        self,
        *,
        endpoint: str,
        model: str,
        api_key: str,
        timeout_seconds: float,
        max_tokens: int,
        temperature: float,
        top_p: float,
    ) -> None:
        self.endpoint = endpoint
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p

    def generate(self, prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "n": 1,
        }
        request = urllib.request.Request(
            f"{self.endpoint}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=self._headers(),
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers


def _run_pending(
    pending: list[dict[str, Any]],
    *,
    handle: Any,
    client: OpenAIChatClient,
    run_id: str,
    baseline_name: str,
    concurrency: int,
    max_retries: int,
    progress_every: int,
    total: int,
    already_done: int,
) -> None:
    done = already_done
    if concurrency <= 1:
        for row in pending:
            record = _record_for_prompt(row, client, run_id, baseline_name, max_retries)
            _append_jsonl(handle, record)
            done += 1
            _print_progress(done, total, progress_every)
        return

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(_record_for_prompt, row, client, run_id, baseline_name, max_retries)
            for row in pending
        ]
        for future in concurrent.futures.as_completed(futures):
            record = future.result()
            _append_jsonl(handle, record)
            done += 1
            _print_progress(done, total, progress_every)


def _record_for_prompt(
    row: dict[str, Any],
    client: OpenAIChatClient,
    run_id: str,
    baseline_name: str,
    max_retries: int,
) -> dict[str, Any]:
    prompt = str(row["prompt"])
    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.generate(prompt)
            choice = response.get("choices", [{}])[0]
            message = choice.get("message", {})
            return {
                "prompt_id": row["prompt_id"],
                "prompt": prompt,
                "kind": "baseline",
                "baseline": baseline_name,
                "run_id": run_id,
                "text": str(message.get("content", "")),
                "model": client.model,
                "metadata": {
                    **dict(row.get("metadata", {})),
                    "generator_logprob": choice.get("logprob", choice.get("logprobs", 0.0)),
                    "finish_reason": choice.get("finish_reason"),
                    "attempt": attempt,
                },
            }
        except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            last_error = exc
            time.sleep(min(2**attempt, 30))
    raise RuntimeError(f"generation failed for prompt_id={row.get('prompt_id')}") from last_error


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


def _print_progress(done: int, total: int, progress_every: int) -> None:
    if done == total or done % progress_every == 0:
        print(f"[baseline] {done}/{total} records written", flush=True)


def _git_commit() -> str:
    git_head = Path(".git/HEAD")
    if not git_head.exists():
        return "not-a-git-checkout"
    return os.popen("git rev-parse HEAD 2>/dev/null").read().strip() or "unknown"


if __name__ == "__main__":
    raise SystemExit(main())

