#!/usr/bin/env bash
set -euo pipefail
cd /data/lry_machine_learning/ttc_dense_verifier
. .venv-vllm/bin/activate
export PYTHONPATH=src
export GENERATOR_ENDPOINT=http://127.0.0.1:8000/v1
export GENERATOR_MODEL=Qwen2.5-32B-Instruct
mkdir -p outputs/logs data/generated_positive data/generated_negative data/preference data/training/rm data/training/sft
printf "run_id=%s\nstarted_at=%s\ncommit=47e4d0e\n" "20260603_031622" "$(date -Is)" > outputs/logs/current_generation_run.env
python -m ttc_dense_verifier.cli run-generation-requests \
  --input data/generated_positive/positive_generation_requests.jsonl \
  --output data/generated_positive/positive_answers.jsonl \
  --endpoint "$GENERATOR_ENDPOINT" \
  --model "$GENERATOR_MODEL" \
  --timeout-seconds 1800 \
  --max-tokens 512 \
  --temperature 0.2 \
  --resume \
  --progress-every 10
python -m ttc_dense_verifier.cli run-generation-requests \
  --input data/generated_negative/negative_generation_requests.jsonl \
  --output data/generated_negative/negative_answers.jsonl \
  --endpoint "$GENERATOR_ENDPOINT" \
  --model "$GENERATOR_MODEL" \
  --timeout-seconds 1800 \
  --max-tokens 512 \
  --temperature 0.7 \
  --resume \
  --progress-every 10
rm -rf data/preference data/training/rm data/training/sft
python -m ttc_dense_verifier.cli prepare-preferences \
  --questions data/raw_questions/questions.jsonl \
  --positive data/generated_positive/positive_answers.jsonl \
  --negative data/generated_negative/negative_answers.jsonl \
  --output-dir data/preference \
  --seed 13
python -m ttc_dense_verifier.cli export-rm-dataset \
  --train data/preference/train_preference.jsonl \
  --val data/preference/val_preference.jsonl \
  --output-dir data/training/rm \
  --dataset-name ttc_rm
python -m ttc_dense_verifier.cli export-sft-dataset \
  --input data/preference/train_preference.jsonl \
  --output data/training/sft/train_sft.jsonl
python -m ttc_dense_verifier.cli validate-training-inputs \
  --rm-config configs/training/verifier_rm_qwen7b.yaml \
  --sft-config configs/training/generator_sft_qwen32b_lora.yaml \
  --rm-dataset-dir data/training/rm \
  --sft-dataset-dir data/training/sft \
  --output outputs/logs/training_input_validation_20260603_031622.json
printf "finished_at=%s\n" "$(date -Is)" >> outputs/logs/current_generation_run.env
