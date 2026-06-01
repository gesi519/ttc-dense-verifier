#!/usr/bin/env bash
set -euo pipefail

cd "/data/lry_machine_learning/ttc_dense_verifier"
export TTC_RUN_ID="${TTC_RUN_ID:-service-$(date +%Y%m%d-%H%M%S)}"
export VERIFIER_PORT="${VERIFIER_PORT:-8001}"
export VERIFIER_HOST="${VERIFIER_HOST:-0.0.0.0}"
export VERIFIER_CHECKPOINT_DIR="${VERIFIER_CHECKPOINT_DIR:-checkpoints/verifier_qwen7b_rm}"
VERIFIER_ENDPOINT=http://127.0.0.1:${VERIFIER_PORT}/score
export VERIFIER_ENDPOINT
mkdir -p outputs/logs

cat > outputs/logs/verifier_service_${TTC_RUN_ID}.env <<SERVICE_ENV
VERIFIER_ENDPOINT=${VERIFIER_ENDPOINT}
VERIFIER_MODEL=${VERIFIER_MODEL:-Qwen2.5-7B-RM}
VERIFIER_CHECKPOINT_DIR=${VERIFIER_CHECKPOINT_DIR}
VERIFIER_PORT=${VERIFIER_PORT}
SERVICE_ENV

tmux kill-session -t ttc_verifier_service 2>/dev/null || true
tmux new-session -d -s ttc_verifier_service "cd \"/data/lry_machine_learning/ttc_dense_verifier\"; export VERIFIER_HOST=\"${VERIFIER_HOST}\"; export VERIFIER_PORT=\"${VERIFIER_PORT}\"; export VERIFIER_CHECKPOINT_DIR=\"${VERIFIER_CHECKPOINT_DIR}\"; export CUDA_VISIBLE_DEVICES=\"${VERIFIER_CUDA_VISIBLE_DEVICES:-6,7}\"; ${VERIFIER_SERVICE_COMMAND:?set VERIFIER_SERVICE_COMMAND} > \"outputs/logs/verifier_service_${TTC_RUN_ID}.log\" 2>&1"

echo "VERIFIER_ENDPOINT=${VERIFIER_ENDPOINT}"
echo "[service] verifier logs: outputs/logs/verifier_service_${TTC_RUN_ID}.log"
