#!/usr/bin/env bash
set -euo pipefail

CONFIG=""
DRY_RUN=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      CONFIG="${2:?missing value for --config}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    *)
      echo "unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$CONFIG" ]]; then
  echo "--config is required" >&2
  exit 2
fi

cd /data/lry_machine_learning/ttc_dense_verifier

eval "$(
  python3 - "$CONFIG" <<'PY'
import json
import shlex
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    cfg = json.load(handle)

for key, value in {
    "RUN_ID": cfg["run_id"],
    "SFT_OUTPUT": cfg["sft_output"],
    "TEST_PROMPTS": cfg["test_prompts"],
    "RAW_SERVICE_CONFIG": cfg["raw_service_config"],
    "TTC_SMOKE_CONFIG": cfg["ttc_smoke_config"],
    "TTC_FULL_CONFIG": cfg["ttc_full_config"],
    "EXPECTED_COUNT": str(cfg.get("expected_count", 500)),
    "POLL_SECONDS": str(cfg.get("poll_seconds", 180)),
    "RAW_READY_TIMEOUT_SECONDS": str(cfg.get("raw_ready_timeout_seconds", 900)),
    "GENERATOR_ENDPOINT": cfg.get("generator_endpoint", "http://127.0.0.1:8000/v1"),
    "VERIFIER_ENDPOINT": cfg.get("verifier_endpoint", "http://127.0.0.1:8001/score"),
    "LOG_PATH": cfg.get("log_path", f"outputs/logs/post_sft_ttc_pipeline_{cfg['run_id']}.log"),
}.items():
    print(f"{key}={shlex.quote(value)}")
PY
)"

mkdir -p "$(dirname "$LOG_PATH")" outputs/logs outputs/ttc runs/ttc

echo "run_id=${RUN_ID}"
echo "config=${CONFIG}"
echo "sft_output=${SFT_OUTPUT}"
echo "raw_service_config=${RAW_SERVICE_CONFIG}"
echo "ttc_smoke_config=${TTC_SMOKE_CONFIG}"
echo "ttc_full_config=${TTC_FULL_CONFIG}"
echo "log_path=${LOG_PATH}"

if [[ "$DRY_RUN" == "1" ]]; then
  exit 0
fi

wait_for_sft() {
  while true; do
    local lines
    lines=$(wc -l < "$SFT_OUTPUT" 2>/dev/null || echo 0)
    echo "[watch] $(date -Is) sft_lines=${lines}/${EXPECTED_COUNT}"
    if [[ "$lines" -ge "$EXPECTED_COUNT" ]]; then
      return 0
    fi
    if ! tmux has-session -t ttc_sft32b_baseline_full 2>/dev/null; then
      echo "[watch] SFT tmux exited before expected count" >&2
      tail -120 outputs/logs/sft_32b_baseline_full_tmux.log 2>/dev/null || true
      return 1
    fi
    sleep "$POLL_SECONDS"
  done
}

validate_jsonl_complete() {
  local output="$1"
  local expected="${2:-$EXPECTED_COUNT}"
  python3 - "$TEST_PROMPTS" "$output" "$expected" <<'PY'
import json
import sys
from pathlib import Path

prompts = [json.loads(line) for line in Path(sys.argv[1]).open() if line.strip()]
rows = [json.loads(line) for line in Path(sys.argv[2]).open() if line.strip()]
expected = int(sys.argv[3])
prompt_ids = [str(row["prompt_id"]) for row in prompts[:expected]]
row_ids = [str(row.get("prompt_id", "")) for row in rows]
missing = sorted(set(prompt_ids) - set(row_ids))
extra = sorted(set(row_ids) - set(prompt_ids))
duplicates = sorted({prompt_id for prompt_id in row_ids if row_ids.count(prompt_id) > 1})
empty = [str(row.get("prompt_id", "")) for row in rows if not str(row.get("text", row.get("final_answer", ""))).strip()]
report = {
    "expected": expected,
    "rows": len(rows),
    "missing": missing[:20],
    "extra": extra[:20],
    "duplicates": duplicates[:20],
    "empty": empty[:20],
    "ok": len(rows) == expected and not missing and not extra and not duplicates and not empty,
}
print(json.dumps(report, ensure_ascii=False, indent=2))
raise SystemExit(0 if report["ok"] else 1)
PY
}

wait_for_raw_generator() {
  local deadline=$(( $(date +%s) + RAW_READY_TIMEOUT_SECONDS ))
  while [[ "$(date +%s)" -lt "$deadline" ]]; do
    if curl -fsS "${GENERATOR_ENDPOINT}/models" >/tmp/ttc_raw_models.json 2>/tmp/ttc_raw_models.err; then
      cat /tmp/ttc_raw_models.json
      echo
      return 0
    fi
    if ! tmux has-session -t ttc_generator_baseline_service 2>/dev/null; then
      echo "[watch] raw generator service exited before ready" >&2
      tail -160 outputs/logs/generator_baseline_service_raw_32b_P13RAW_FULL_20260605_061600.log 2>/dev/null || true
      return 1
    fi
    sleep 10
  done
  echo "[watch] raw generator did not become ready before timeout" >&2
  cat /tmp/ttc_raw_models.err 2>/dev/null || true
  return 1
}

main() {
  wait_for_sft
  echo "[watch] validating SFT output"
  validate_jsonl_complete "$SFT_OUTPUT"

  echo "[watch] starting raw generator service"
  scripts/remote_infer/start_generator_vllm_baseline.sh --config "$RAW_SERVICE_CONFIG"
  wait_for_raw_generator

  echo "[watch] probing verifier"
  curl -fsS "$VERIFIER_ENDPOINT" \
    -H "Content-Type: application/json" \
    --data '{"prompt":"Explain memcpy versus memmove in C.","answer":"memmove is safe for overlapping regions; memcpy has undefined behavior when source and destination overlap."}'
  echo

  echo "[watch] running TTC smoke"
  PYTHONPATH=src .venv-train/bin/python scripts/remote_infer/run_ttc_incremental.py --config "$TTC_SMOKE_CONFIG"
  smoke_expected=$(python3 - "$TTC_SMOKE_CONFIG" <<'PY'
import json
import sys
cfg = json.load(open(sys.argv[1]))
print(cfg.get("limit") or 0)
PY
)
  if [[ "$smoke_expected" == "0" ]]; then
    smoke_expected="$EXPECTED_COUNT"
  fi
  validate_jsonl_complete "$(python3 - "$TTC_SMOKE_CONFIG" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["paths"]["output_jsonl"])
PY
)" "$smoke_expected"

  echo "[watch] starting TTC full"
  tmux kill-session -t ttc_ttc_beam_raw32b_full 2>/dev/null || true
  tmux new-session -d -s ttc_ttc_beam_raw32b_full \
    "cd /data/lry_machine_learning/ttc_dense_verifier; PYTHONPATH=src .venv-train/bin/python scripts/remote_infer/run_ttc_incremental.py --config '$TTC_FULL_CONFIG' > outputs/logs/ttc_beam_raw32b_full_tmux.log 2>&1"
  echo "[watch] TTC full tmux started: ttc_ttc_beam_raw32b_full"
}

main 2>&1 | tee -a "$LOG_PATH"
