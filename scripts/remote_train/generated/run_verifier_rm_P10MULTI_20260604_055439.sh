#!/usr/bin/env bash
set -euo pipefail
cd /data/lry_machine_learning/ttc_dense_verifier
export RUN_ID=P10MULTI_20260604_055439
export HF_HOME=/data/lry_machine_learning/huggingface
export TRANSFORMERS_CACHE=/data/lry_machine_learning/huggingface/transformers
export HF_DATASETS_CACHE=/data/lry_machine_learning/huggingface/datasets
export UV_CACHE_DIR=/data/lry_machine_learning/uv-cache
export PYTHONPATH=src
export PATH=/data/lry_machine_learning/ttc_dense_verifier/.venv-train/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/games:/usr/local/games:/snap/bin
export NCCL_P2P_DISABLE=1
export NCCL_IB_DISABLE=1
export FORCE_TORCHRUN=1
export NPROC_PER_NODE=3
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-1,4,5}"
CONFIG=configs/training/generated/verifier_rm_qwen7b_P10MULTI_20260604_055439.yaml
LOG=outputs/logs/verifier_rm_training_P10MULTI_20260604_055439.log
.venv-train/bin/python -m ttc_dense_verifier.cli validate-training-inputs \
  --rm-config "$CONFIG" \
  --sft-config configs/training/generator_sft_qwen32b_lora.yaml \
  --rm-dataset-dir data/training/rm \
  --sft-dataset-dir data/training/sft \
  --output outputs/logs/training_input_validation_P10MULTI_20260604_055439.json
.venv-train/bin/llamafactory-cli train "$CONFIG" 2>&1 | tee "$LOG"
.venv-train/bin/python -m ttc_dense_verifier.cli export-training-summary \
  --config "$CONFIG" \
  --output outputs/logs/verifier_rm_metrics_P10MULTI_20260604_055439.json \
  --label verifier_rm_multi3
