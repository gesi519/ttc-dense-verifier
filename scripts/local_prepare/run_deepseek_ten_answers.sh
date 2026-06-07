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

COUNT="${DEEPSEEK_TEN_COUNT:-10}"
CONCURRENCY="${DEEPSEEK_TEN_CONCURRENCY:-4}"
ENDPOINT="${DEEPSEEK_ENDPOINT:-https://api.deepseek.com}"
MODEL="${DEEPSEEK_MODEL:-deepseek-v4-pro}"
TIMEOUT_SECONDS="${DEEPSEEK_TIMEOUT_SECONDS:-1800}"
MAX_RETRIES="${DEEPSEEK_MAX_RETRIES:-3}"
MAX_TOKENS="${DEEPSEEK_TEN_MAX_TOKENS:-4096}"
TEMPERATURE="${DEEPSEEK_TEN_TEMPERATURE:-0.2}"

INPUT="data/generated_positive/positive_generation_requests.jsonl"
"${PYTHON_BIN}" -m ttc_dense_verifier.cli build-generation-requests \
  --questions data/raw_questions/questions.jsonl \
  --mode positive \
  --model "${MODEL}" \
  --output "${INPUT}"

mkdir -p outputs/ten_check outputs/logs
RUN_ID="$(date +%Y%m%d_%H%M%S)"
REQUEST_FILE="outputs/ten_check/positive_requests_${COUNT}_${RUN_ID}.jsonl"
OUTPUT_FILE="outputs/ten_check/positive_answers_${COUNT}_${RUN_ID}.jsonl"

head -n "${COUNT}" "${INPUT}" > "${REQUEST_FILE}"
rm -f "${OUTPUT_FILE}"

"${PYTHON_BIN}" -m ttc_dense_verifier.cli run-generation-requests \
  --input "${REQUEST_FILE}" \
  --output "${OUTPUT_FILE}" \
  --endpoint "${ENDPOINT}" \
  --model "${MODEL}" \
  --timeout-seconds "${TIMEOUT_SECONDS}" \
  --max-tokens "${MAX_TOKENS}" \
  --temperature "${TEMPERATURE}" \
  --resume \
  --concurrency "${CONCURRENCY}" \
  --max-retries "${MAX_RETRIES}" \
  --progress-every 1 \
  --deepseek-disable-thinking

"${PYTHON_BIN}" scripts/local_prepare/validate_answer_file.py "${OUTPUT_FILE}" "${COUNT}"
echo "output=${OUTPUT_FILE}"
