#!/usr/bin/env bash
set -euo pipefail
cd /data/lry_machine_learning/ttc_dense_verifier
export HF_HOME=/data/lry_machine_learning/huggingface
export TRANSFORMERS_CACHE=/data/lry_machine_learning/huggingface/transformers
export HF_DATASETS_CACHE=/data/lry_machine_learning/huggingface/datasets
export UV_CACHE_DIR=/data/lry_machine_learning/uv-cache
export PYTHONPATH=src
RUN_ID="$(cat outputs/logs/current_verifier_training_run_id.txt)"
TRAIN_SCRIPT="scripts/remote_train/generated/run_verifier_rm_${RUN_ID}.sh"
WATCH_LOG="outputs/logs/verifier_rm_watch_${RUN_ID}.log"
MODEL_DIR="/data/lry_machine_learning/models/Qwen2.5-7B-Instruct"
required_model_files() {
  test -s "${MODEL_DIR}/config.json" && \
  test -s "${MODEL_DIR}/tokenizer.json" && \
  test -s "${MODEL_DIR}/model.safetensors.index.json" && \
  test -s "${MODEL_DIR}/model-00001-of-00004.safetensors" && \
  test -s "${MODEL_DIR}/model-00002-of-00004.safetensors" && \
  test -s "${MODEL_DIR}/model-00003-of-00004.safetensors" && \
  test -s "${MODEL_DIR}/model-00004-of-00004.safetensors"
}
llamafactory_ready() {
  test -x .venv-train/bin/llamafactory-cli
}
gpu_ready() {
  python3 - <<"PY"
import subprocess, sys
out = subprocess.check_output([
    "nvidia-smi",
    "--query-gpu=index,memory.used,utilization.gpu",
    "--format=csv,noheader,nounits",
], text=True)
free=[]
for line in out.strip().splitlines():
    idx, mem, util = [part.strip() for part in line.split(",")]
    if int(mem) < 9000 and int(util) < 10:
        free.append(idx)
if len(free) >= 4:
    print(",".join(free[:4]))
    sys.exit(0)
print("not enough free GPUs: " + ",".join(free))
sys.exit(1)
PY
}
{
  echo "watch_started_at=$(date -Is)"
  echo "run_id=${RUN_ID}"
  while true; do
    echo "[watch] $(date -Is) checking prerequisites"
    if ! required_model_files; then
      echo "[watch] model not complete yet"
      sleep 300
      continue
    fi
    if ! llamafactory_ready; then
      echo "[watch] llamafactory env not ready yet"
      sleep 300
      continue
    fi
    if ! FREE_GPUS=$(gpu_ready); then
      echo "[watch] gpu not ready: ${FREE_GPUS:-none}"
      sleep 300
      continue
    fi
    echo "[watch] starting training on GPUs ${FREE_GPUS}"
    export CUDA_VISIBLE_DEVICES="${FREE_GPUS}"
    tmux kill-session -t ttc_verifier_rm_training 2>/dev/null || true
    tmux new-session -d -s ttc_verifier_rm_training "cd /data/lry_machine_learning/ttc_dense_verifier; export CUDA_VISIBLE_DEVICES=\"${FREE_GPUS}\"; bash ${TRAIN_SCRIPT} > outputs/logs/verifier_rm_tmux_${RUN_ID}.log 2>&1"
    echo "[watch] training tmux started at $(date -Is)"
    exit 0
  done
} >> "${WATCH_LOG}" 2>&1
