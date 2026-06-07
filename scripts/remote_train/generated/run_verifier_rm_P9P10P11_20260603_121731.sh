#!/usr/bin/env bash
set -euo pipefail
cd /data/lry_machine_learning/ttc_dense_verifier
export RUN_ID=P9P10P11_20260603_121731
export HF_HOME=/data/lry_machine_learning/huggingface
export TRANSFORMERS_CACHE=/data/lry_machine_learning/huggingface/transformers
export HF_DATASETS_CACHE=/data/lry_machine_learning/huggingface/datasets
export UV_CACHE_DIR=/data/lry_machine_learning/uv-cache
export PYTHONPATH=src
export NCCL_P2P_DISABLE=1
export NCCL_IB_DISABLE=1
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0,1,2,3}"
CONFIG=configs/training/generated/verifier_rm_qwen7b_P9P10P11_20260603_121731.yaml
LOG=outputs/logs/verifier_rm_training_P9P10P11_20260603_121731.log
.venv-train/bin/python -m ttc_dense_verifier.cli validate-training-inputs \
  --rm-config "$CONFIG" \
  --sft-config configs/training/generator_sft_qwen32b_lora.yaml \
  --rm-dataset-dir data/training/rm \
  --sft-dataset-dir data/training/sft \
  --output outputs/logs/training_input_validation_P9P10P11_20260603_121731.json
.venv-train/bin/llamafactory-cli train "$CONFIG" 2>&1 | tee "$LOG"
.venv-train/bin/python -m ttc_dense_verifier.cli export-training-summary \
  --config "$CONFIG" \
  --output outputs/logs/verifier_rm_metrics_P9P10P11_20260603_121731.json \
  --label verifier_rm
