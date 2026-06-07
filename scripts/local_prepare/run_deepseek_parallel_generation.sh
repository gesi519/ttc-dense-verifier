#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

if [ -f .env.local ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env.local
  set +a
fi

if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  echo "Set DEEPSEEK_API_KEY before running this script, or put it in .env.local." >&2
  exit 2
fi

export PYTHONPATH="${PYTHONPATH:-src}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

ENDPOINT="${DEEPSEEK_ENDPOINT:-https://api.deepseek.com}"
MODEL="${DEEPSEEK_MODEL:-deepseek-v4-pro}"
CONCURRENCY="${DEEPSEEK_CONCURRENCY:-64}"
TIMEOUT_SECONDS="${DEEPSEEK_TIMEOUT_SECONDS:-1800}"
MAX_RETRIES="${DEEPSEEK_MAX_RETRIES:-5}"
POSITIVE_MAX_TOKENS="${DEEPSEEK_POSITIVE_MAX_TOKENS:-4096}"
NEGATIVE_MAX_TOKENS="${DEEPSEEK_NEGATIVE_MAX_TOKENS:-4096}"
POSITIVE_TEMPERATURE="${DEEPSEEK_POSITIVE_TEMPERATURE:-0.2}"
NEGATIVE_TEMPERATURE="${DEEPSEEK_NEGATIVE_TEMPERATURE:-0.7}"

mkdir -p outputs/logs data/generated_positive data/generated_negative data/preference data/training/rm data/training/sft
RUN_ID="$(date +%Y%m%d_%H%M%S)"
LOG="outputs/logs/deepseek_parallel_generation_${RUN_ID}.log"
timestamp() {
  date +"%Y-%m-%dT%H:%M:%S%z"
}

{
  echo "run_id=${RUN_ID}"
  echo "endpoint=${ENDPOINT}"
  echo "model=${MODEL}"
  echo "concurrency=${CONCURRENCY}"
  echo "started_at=$(timestamp)"

  echo "[stage] build positive generation requests"
  "${PYTHON_BIN}" -m ttc_dense_verifier.cli build-generation-requests \
    --questions data/raw_questions/questions.jsonl \
    --mode positive \
    --model "${MODEL}" \
    --output data/generated_positive/positive_generation_requests.jsonl

  echo "[stage] build negative generation requests"
  "${PYTHON_BIN}" -m ttc_dense_verifier.cli build-generation-requests \
    --questions data/raw_questions/questions.jsonl \
    --mode negative \
    --model "${MODEL}" \
    --output data/generated_negative/negative_generation_requests.jsonl

  echo "[stage] generate positive answers"
  "${PYTHON_BIN}" -m ttc_dense_verifier.cli run-generation-requests \
    --input data/generated_positive/positive_generation_requests.jsonl \
    --output data/generated_positive/positive_answers.jsonl \
    --endpoint "${ENDPOINT}" \
    --model "${MODEL}" \
    --timeout-seconds "${TIMEOUT_SECONDS}" \
    --max-tokens "${POSITIVE_MAX_TOKENS}" \
    --temperature "${POSITIVE_TEMPERATURE}" \
    --resume \
    --concurrency "${CONCURRENCY}" \
    --max-retries "${MAX_RETRIES}" \
    --progress-every 25 \
    --deepseek-disable-thinking

  echo "[stage] generate negative answers"
  "${PYTHON_BIN}" -m ttc_dense_verifier.cli run-generation-requests \
    --input data/generated_negative/negative_generation_requests.jsonl \
    --output data/generated_negative/negative_answers.jsonl \
    --endpoint "${ENDPOINT}" \
    --model "${MODEL}" \
    --timeout-seconds "${TIMEOUT_SECONDS}" \
    --max-tokens "${NEGATIVE_MAX_TOKENS}" \
    --temperature "${NEGATIVE_TEMPERATURE}" \
    --resume \
    --concurrency "${CONCURRENCY}" \
    --max-retries "${MAX_RETRIES}" \
    --progress-every 25 \
    --deepseek-disable-thinking

  echo "[stage] prepare preference splits"
  rm -rf data/preference data/training/rm data/training/sft

  "${PYTHON_BIN}" -m ttc_dense_verifier.cli prepare-preferences \
    --questions data/raw_questions/questions.jsonl \
    --positive data/generated_positive/positive_answers.jsonl \
    --negative data/generated_negative/negative_answers.jsonl \
    --output-dir data/preference \
    --seed 13

  echo "[stage] export reward-model dataset"
  "${PYTHON_BIN}" -m ttc_dense_verifier.cli export-rm-dataset \
    --train data/preference/train_preference.jsonl \
    --val data/preference/val_preference.jsonl \
    --output-dir data/training/rm \
    --dataset-name ttc_rm

  echo "[stage] export sft dataset"
  "${PYTHON_BIN}" -m ttc_dense_verifier.cli export-sft-dataset \
    --input data/preference/train_preference.jsonl \
    --output data/training/sft/train_sft.jsonl

  echo "[stage] validate training inputs"
  "${PYTHON_BIN}" -m ttc_dense_verifier.cli validate-training-inputs \
    --rm-config configs/training/verifier_rm_qwen7b.yaml \
    --sft-config configs/training/generator_sft_qwen32b_lora.yaml \
    --rm-dataset-dir data/training/rm \
    --sft-dataset-dir data/training/sft \
    --output "outputs/logs/deepseek_training_input_validation_${RUN_ID}.json"

  echo "finished_at=$(timestamp)"
} 2>&1 | tee "${LOG}"

echo "Log written to ${LOG}"
