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

service = cfg["service"]
baseline = cfg["baseline"]
for key, value in {
    "RUN_ID": cfg["run_id"],
    "BASELINE_NAME": baseline["name"],
    "MODEL_PATH": baseline["model_path"],
    "SERVED_MODEL_NAME": baseline["served_model_name"],
    "CUDA_VISIBLE_DEVICES_VALUE": service.get("cuda_visible_devices", "1,2,3"),
    "TENSOR_PARALLEL_SIZE": str(service.get("tensor_parallel_size", 3)),
    "HOST": service.get("host", "0.0.0.0"),
    "PORT": str(service.get("port", 8000)),
    "SESSION_NAME": service.get("session_name", "ttc_generator_baseline_service"),
    "LOG_DIR": service.get("log_dir", "outputs/logs"),
    "VENV": service.get("venv", ".venv-vllm"),
    "DTYPE": service.get("dtype", "bfloat16"),
    "MAX_MODEL_LEN": str(service.get("max_model_len", 4096)),
    "GPU_MEMORY_UTILIZATION": str(service.get("gpu_memory_utilization", 0.90)),
    "ENFORCE_EAGER": "1" if service.get("enforce_eager", False) else "0",
    "LORA_NAME": baseline.get("lora_name", ""),
    "LORA_PATH": baseline.get("lora_path", ""),
}.items():
    print(f"{key}={shlex.quote(value)}")
PY
)"

mkdir -p "$LOG_DIR"
SERVICE_LOG="${LOG_DIR}/generator_baseline_service_${BASELINE_NAME}_${RUN_ID}.log"
SERVICE_ENV="${LOG_DIR}/generator_baseline_service_${BASELINE_NAME}_${RUN_ID}.env"
ENDPOINT="http://127.0.0.1:${PORT}/v1"

cat > "$SERVICE_ENV" <<ENV
RUN_ID=${RUN_ID}
BASELINE_NAME=${BASELINE_NAME}
GENERATOR_ENDPOINT=${ENDPOINT}
SERVED_MODEL_NAME=${SERVED_MODEL_NAME}
MODEL_PATH=${MODEL_PATH}
LORA_NAME=${LORA_NAME}
LORA_PATH=${LORA_PATH}
CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES_VALUE}
TENSOR_PARALLEL_SIZE=${TENSOR_PARALLEL_SIZE}
CONFIG=${CONFIG}
ENV

CMD=(
  "${VENV}/bin/vllm" serve "$MODEL_PATH"
  --served-model-name "$SERVED_MODEL_NAME"
  --host "$HOST"
  --port "$PORT"
  --tensor-parallel-size "$TENSOR_PARALLEL_SIZE"
  --dtype "$DTYPE"
  --max-model-len "$MAX_MODEL_LEN"
  --gpu-memory-utilization "$GPU_MEMORY_UTILIZATION"
)

if [[ "$ENFORCE_EAGER" == "1" ]]; then
  CMD+=(--enforce-eager)
fi

if [[ -n "$LORA_NAME" && -n "$LORA_PATH" ]]; then
  CMD+=(--enable-lora --lora-modules "${LORA_NAME}=${LORA_PATH}")
fi

printf 'GENERATOR_ENDPOINT=%s\n' "$ENDPOINT"
printf 'SERVED_MODEL_NAME=%s\n' "$SERVED_MODEL_NAME"
printf 'SERVICE_LOG=%s\n' "$SERVICE_LOG"
printf 'SESSION_NAME=%s\n' "$SESSION_NAME"
printf 'COMMAND=%q ' env "CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES_VALUE}" "${CMD[@]}"
printf '\n'

if [[ "$DRY_RUN" == "1" ]]; then
  exit 0
fi

tmux kill-session -t "$SESSION_NAME" 2>/dev/null || true
tmux new-session -d -s "$SESSION_NAME" \
  "cd /data/lry_machine_learning/ttc_dense_verifier; env CUDA_VISIBLE_DEVICES='${CUDA_VISIBLE_DEVICES_VALUE}' ${CMD[*]} > '${SERVICE_LOG}' 2>&1"
