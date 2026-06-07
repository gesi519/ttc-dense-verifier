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

cfg = json.load(open(sys.argv[1], encoding="utf-8"))
for key, value in {
    "RUN_ID": cfg["run_id"],
    "EXPECTED_COUNT": str(cfg.get("expected_count", 500)),
    "POLL_SECONDS": str(cfg.get("poll_seconds", 180)),
    "TTC_OUTPUT": cfg["ttc_output"],
    "TTC_TRACE": cfg["ttc_trace"],
    "MERGE_CONFIG": cfg["merge_config"],
    "MERGED_OUTPUT": cfg["merged_output"],
    "STATIC_OUTPUT_DIR": cfg["static_output_dir"],
    "ASSET_OUTPUT_DIR": cfg["asset_output_dir"],
    "JUDGE_MODEL": cfg.get("judge_model", "remote-judge-model"),
    "LOG_PATH": cfg.get("log_path", f"outputs/logs/watch_ttc_then_eval_{cfg['run_id']}.log"),
}.items():
    print(f"{key}={shlex.quote(value)}")
PY
)"

mkdir -p "$(dirname "$LOG_PATH")" "$STATIC_OUTPUT_DIR" "$ASSET_OUTPUT_DIR"

echo "run_id=${RUN_ID}"
echo "config=${CONFIG}"
echo "ttc_output=${TTC_OUTPUT}"
echo "merge_config=${MERGE_CONFIG}"
echo "merged_output=${MERGED_OUTPUT}"
echo "static_output_dir=${STATIC_OUTPUT_DIR}"
echo "asset_output_dir=${ASSET_OUTPUT_DIR}"
echo "log_path=${LOG_PATH}"

if [[ "$DRY_RUN" == "1" ]]; then
  exit 0
fi

wait_for_ttc() {
  while true; do
    local lines traces
    lines=$(wc -l < "$TTC_OUTPUT" 2>/dev/null || echo 0)
    traces=$(wc -l < "$TTC_TRACE" 2>/dev/null || echo 0)
    echo "[watch-eval] $(date -Is) ttc_lines=${lines}/${EXPECTED_COUNT} trace_lines=${traces}/${EXPECTED_COUNT}"
    if [[ "$lines" -ge "$EXPECTED_COUNT" && "$traces" -ge "$EXPECTED_COUNT" ]]; then
      return 0
    fi
    if ! tmux has-session -t ttc_ttc_beam_raw32b_full 2>/dev/null; then
      echo "[watch-eval] TTC tmux exited before expected count" >&2
      tail -160 outputs/logs/ttc_beam_raw32b_full_tmux.log 2>/dev/null || true
      return 1
    fi
    sleep "$POLL_SECONDS"
  done
}

main() {
  wait_for_ttc
  echo "[watch-eval] merging evaluation inputs"
  python3 scripts/remote_eval/merge_eval_inputs.py --config "$MERGE_CONFIG"
  echo "[watch-eval] exporting static metrics"
  PYTHONPATH=src .venv-train/bin/python -m ttc_dense_verifier.cli evaluate-static \
    --input "$MERGED_OUTPUT" \
    --output-dir "$STATIC_OUTPUT_DIR"
  echo "[watch-eval] exporting evaluation assets"
  PYTHONPATH=src .venv-train/bin/python -m ttc_dense_verifier.cli export-evaluation-assets \
    --input "$MERGED_OUTPUT" \
    --output-dir "$ASSET_OUTPUT_DIR" \
    --judge-model "$JUDGE_MODEL"
  echo "[watch-eval] complete"
}

main 2>&1 | tee -a "$LOG_PATH"

