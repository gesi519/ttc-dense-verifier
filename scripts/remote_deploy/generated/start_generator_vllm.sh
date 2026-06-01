#!/usr/bin/env bash
set -euo pipefail

cd "/srv/ttc-dense-verifier"
export TTC_RUN_ID="${TTC_RUN_ID:-service-$(date +%Y%m%d-%H%M%S)}"
export GENERATOR_PORT="${GENERATOR_PORT:-8000}"
export GENERATOR_HOST="${GENERATOR_HOST:-0.0.0.0}"
GENERATOR_ENDPOINT=http://127.0.0.1:${GENERATOR_PORT}/v1
export GENERATOR_ENDPOINT
mkdir -p outputs/logs

cat > outputs/logs/generator_service_${TTC_RUN_ID}.env <<SERVICE_ENV
GENERATOR_ENDPOINT=${GENERATOR_ENDPOINT}
GENERATOR_MODEL=${GENERATOR_MODEL:-Qwen2.5-32B-Instruct}
GENERATOR_MODEL_PATH=${GENERATOR_MODEL_PATH:?set GENERATOR_MODEL_PATH}
GENERATOR_PORT=${GENERATOR_PORT}
GENERATOR_TENSOR_PARALLEL_SIZE=${GENERATOR_TENSOR_PARALLEL_SIZE:-6}
SERVICE_ENV

tmux kill-session -t ttc_generator_service 2>/dev/null || true
tmux new-session -d -s ttc_generator_service "cd \"/srv/ttc-dense-verifier\"; CUDA_VISIBLE_DEVICES=\"${GENERATOR_CUDA_VISIBLE_DEVICES:-0,1,2,3,4,5}\" vllm serve \"${GENERATOR_MODEL_PATH:?set GENERATOR_MODEL_PATH}\" --served-model-name \"${GENERATOR_MODEL:-Qwen2.5-32B-Instruct}\" --host \"${GENERATOR_HOST}\" --port \"${GENERATOR_PORT}\" --tensor-parallel-size \"${GENERATOR_TENSOR_PARALLEL_SIZE:-6}\" > \"outputs/logs/generator_service_${TTC_RUN_ID}.log\" 2>&1"

echo "GENERATOR_ENDPOINT=${GENERATOR_ENDPOINT}"
echo "[service] generator logs: outputs/logs/generator_service_${TTC_RUN_ID}.log"
