#!/usr/bin/env bash
set -euo pipefail
cd /data/lry_machine_learning/ttc_dense_verifier
export HF_HOME=/data/lry_machine_learning/huggingface
export HF_HUB_CACHE=/data/lry_machine_learning/huggingface/hub
export TRANSFORMERS_CACHE=/data/lry_machine_learning/huggingface/transformers
export UV_CACHE_DIR=/data/lry_machine_learning/uv-cache
export NCCL_P2P_DISABLE=1
export NCCL_IB_DISABLE=1
export CUDA_VISIBLE_DEVICES=1,2,3
export FORCE_TORCHRUN=1
export NPROC_PER_NODE=3
export MASTER_PORT=29622
export PATH=/data/lry_machine_learning/ttc_dense_verifier/.venv-train/bin:$PATH
mkdir -p outputs/logs /data/lry_machine_learning/checkpoints/ttc_dense_verifier
printf "%s\n" "P12SFTB_20260604_133514" > outputs/logs/current_generator_sft_run_id.txt
printf "%s\n" "configs/training/generated/generator_sft_qwen32b_lora_P12SFTB_20260604_133514.yaml" > outputs/logs/current_generator_sft_config.txt
printf "%s\n" "/data/lry_machine_learning/checkpoints/ttc_dense_verifier/generator_qwen32b_sft_lora_P12SFTB_20260604_133514" > outputs/logs/current_generator_sft_checkpoint_dir.txt
llamafactory-cli train "configs/training/generated/generator_sft_qwen32b_lora_P12SFTB_20260604_133514.yaml" 2>&1 | tee "outputs/logs/generator_sft_training_P12SFTB_20260604_133514.log"
.venv-train/bin/python - <<PY
import json
from pathlib import Path
run_id = "P12SFTB_20260604_133514"
out = Path("/data/lry_machine_learning/checkpoints/ttc_dense_verifier/generator_qwen32b_sft_lora_P12SFTB_20260604_133514")
state = out / "trainer_state.json"
summary = {"run_id": run_id, "stage": "sft", "label": "generator_qwen32b_sft_lora_control", "config_path": "configs/training/generated/generator_sft_qwen32b_lora_P12SFTB_20260604_133514.yaml", "checkpoint_dir": str(out), "checkpoint_exists": out.exists(), "trainer_state_path": str(state), "ok": state.exists(), "model_name_or_path": "/data/lry_machine_learning/models/Qwen2.5-32B-Instruct"}
if state.exists():
    data = json.loads(state.read_text())
    summary["global_step"] = data.get("global_step")
    summary["best_model_checkpoint"] = data.get("best_model_checkpoint")
    summary["best_metric"] = data.get("best_metric")
    hist = data.get("log_history", [])
    summary["log_history_count"] = len(hist)
    summary["last_metrics"] = hist[-1] if hist else None
Path(f"outputs/logs/generator_sft_metrics_{run_id}.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
PY
