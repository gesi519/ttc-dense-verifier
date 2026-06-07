#!/usr/bin/env bash
set -euo pipefail
cd /data/lry_machine_learning/ttc_dense_verifier
. .venv-vllm/bin/activate
export HF_HOME=/data/lry_machine_learning/huggingface
export HF_TOKEN=$(cat /data/lry_machine_learning/huggingface/token)
export HUGGING_FACE_HUB_TOKEN=$HF_TOKEN
export CUDA_VISIBLE_DEVICES=0,1,2,3,4,5,6,7
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
python -m vllm.entrypoints.openai.api_server \
  --model /data/lry_machine_learning/models/Qwen2.5-32B-Instruct \
  --served-model-name Qwen2.5-32B-Instruct \
  --host 127.0.0.1 \
  --port 8000 \
  --tensor-parallel-size 8 \
  --max-model-len 4096 \
  --max-num-seqs 2 \
  --gpu-memory-utilization 0.28 \
  --trust-remote-code
