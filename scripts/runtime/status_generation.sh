#!/usr/bin/env bash
set -euo pipefail
cd /data/lry_machine_learning/ttc_dense_verifier
RUN_ID=$(cat outputs/logs/current_generation_run_id.txt 2>/dev/null || true)
VLLM_ID=$(cat outputs/logs/current_vllm_run_id.txt 2>/dev/null || true)
echo "time=$(date -Is)"
echo "generation_run_id=$RUN_ID"
echo "vllm_run_id=$VLLM_ID"
echo "sessions="
tmux ls 2>/dev/null || true
echo "counts="
for f in data/generated_positive/positive_answers.jsonl data/generated_negative/negative_answers.jsonl data/preference/train_preference.jsonl data/preference/val_preference.jsonl data/training/rm/train_rm.jsonl data/training/sft/train_sft.jsonl; do
  if [ -f "$f" ]; then echo "$f $(wc -l < $f)"; else echo "$f 0"; fi
done
echo "disk="
df -h /data
echo "gpu="
nvidia-smi --query-gpu=index,memory.used,memory.total,utilization.gpu --format=csv,noheader
echo "recent_generation_log="
if [ -n "$RUN_ID" ] && [ -f "outputs/logs/full_generation_${RUN_ID}.log" ]; then tail -60 "outputs/logs/full_generation_${RUN_ID}.log"; fi
echo "recent_errors="
if [ -n "$RUN_ID" ] && [ -f "outputs/logs/full_generation_${RUN_ID}.log" ]; then grep -n -E "ERROR|Traceback|OutOfMemory|timeout|Connection|RuntimeError" "outputs/logs/full_generation_${RUN_ID}.log" | tail -20 || true; fi
if [ -n "$VLLM_ID" ] && [ -f "outputs/logs/qwen32b_vllm_${VLLM_ID}.log" ]; then grep -n -E "ERROR|Traceback|OutOfMemory|RuntimeError" "outputs/logs/qwen32b_vllm_${VLLM_ID}.log" | tail -20 || true; fi
