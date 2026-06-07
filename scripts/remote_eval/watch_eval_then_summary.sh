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
    "POLL_SECONDS": str(cfg.get("poll_seconds", 180)),
    "MERGED_OUTPUT": cfg["paths"]["merged_output"],
    "ASSET_OUTPUT_DIR": cfg["paths"]["asset_output_dir"],
    "FIGURES_DIR": cfg["paths"]["figures_dir"],
    "SUMMARY_CONFIG": cfg["summary_config"],
    "LOG_PATH": cfg.get("log_path", f"outputs/logs/watch_eval_then_summary_{cfg['run_id']}.log"),
}.items():
    print(f"{key}={shlex.quote(value)}")
PY
)"

mkdir -p "$(dirname "$LOG_PATH")" "$FIGURES_DIR"

echo "run_id=${RUN_ID}"
echo "config=${CONFIG}"
echo "merged_output=${MERGED_OUTPUT}"
echo "asset_output_dir=${ASSET_OUTPUT_DIR}"
echo "figures_dir=${FIGURES_DIR}"
echo "summary_config=${SUMMARY_CONFIG}"
echo "log_path=${LOG_PATH}"

if [[ "$DRY_RUN" == "1" ]]; then
  exit 0
fi

wait_for_eval_assets() {
  while true; do
    local ready=1
    for file in \
      "$ASSET_OUTPUT_DIR/table1_overall_metrics.csv" \
      "$ASSET_OUTPUT_DIR/table2_error_breakdown.csv" \
      "$ASSET_OUTPUT_DIR/table3_latency_cost.csv" \
      "$ASSET_OUTPUT_DIR/human_review.csv" \
      "$ASSET_OUTPUT_DIR/judge_requests.jsonl" \
      "reports/eval/static_raw_sft_ttc/static_metrics_summary.json" \
      "reports/eval/merge_raw_sft_ttc_report.json"; do
      if [[ ! -s "$file" ]]; then
        ready=0
      fi
    done
    echo "[watch-summary] $(date -Is) assets_ready=${ready}"
    if [[ "$ready" == "1" ]]; then
      return 0
    fi
    if ! tmux has-session -t ttc_eval_after_ttc_full 2>/dev/null; then
      echo "[watch-summary] eval watcher exited before assets were ready" >&2
      tail -160 outputs/logs/watch_ttc_then_eval_tmux.log 2>/dev/null || true
      return 1
    fi
    sleep "$POLL_SECONDS"
  done
}

main() {
  wait_for_eval_assets
  echo "[watch-summary] exporting paper figures"
  PYTHONPATH=src .venv-train/bin/python -m ttc_dense_verifier.cli export-paper-figures \
    --input "$MERGED_OUTPUT" \
    --output-dir "$FIGURES_DIR"
  echo "[watch-summary] writing final summary"
  python3 scripts/remote_eval/write_eval_summary.py --config "$SUMMARY_CONFIG"
  echo "[watch-summary] complete"
}

main 2>&1 | tee -a "$LOG_PATH"

