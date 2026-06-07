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

MODE="${DEEPSEEK_SINGLE_MODE:-positive}"
ENDPOINT="${DEEPSEEK_ENDPOINT:-https://api.deepseek.com}"
MODEL="${DEEPSEEK_MODEL:-deepseek-v4-pro}"
TIMEOUT_SECONDS="${DEEPSEEK_TIMEOUT_SECONDS:-1800}"
MAX_RETRIES="${DEEPSEEK_MAX_RETRIES:-3}"
MAX_TOKENS="${DEEPSEEK_SINGLE_MAX_TOKENS:-4096}"
TEMPERATURE="${DEEPSEEK_SINGLE_TEMPERATURE:-0.2}"
REQUEST_INDEX="${DEEPSEEK_SINGLE_INDEX:-1}"

if [ "${MODE}" = "positive" ]; then
  INPUT="data/generated_positive/positive_generation_requests.jsonl"
  "${PYTHON_BIN}" -m ttc_dense_verifier.cli build-generation-requests \
    --questions data/raw_questions/questions.jsonl \
    --mode positive \
    --model "${MODEL}" \
    --output "${INPUT}"
else
  INPUT="data/generated_negative/negative_generation_requests.jsonl"
  "${PYTHON_BIN}" -m ttc_dense_verifier.cli build-generation-requests \
    --questions data/raw_questions/questions.jsonl \
    --mode negative \
    --model "${MODEL}" \
    --output "${INPUT}"
fi

mkdir -p outputs/single_check outputs/logs
RUN_ID="$(date +%Y%m%d_%H%M%S)"
REQUEST_FILE="outputs/single_check/${MODE}_request_${REQUEST_INDEX}_${RUN_ID}.jsonl"
OUTPUT_FILE="outputs/single_check/${MODE}_answer_${REQUEST_INDEX}_${RUN_ID}.jsonl"

sed -n "${REQUEST_INDEX}p" "${INPUT}" > "${REQUEST_FILE}"
if [ ! -s "${REQUEST_FILE}" ]; then
  echo "No request at line ${REQUEST_INDEX} in ${INPUT}" >&2
  exit 3
fi

"${PYTHON_BIN}" -m ttc_dense_verifier.cli run-generation-requests \
  --input "${REQUEST_FILE}" \
  --output "${OUTPUT_FILE}" \
  --endpoint "${ENDPOINT}" \
  --model "${MODEL}" \
  --timeout-seconds "${TIMEOUT_SECONDS}" \
  --max-tokens "${MAX_TOKENS}" \
  --temperature "${TEMPERATURE}" \
  --resume \
  --concurrency 1 \
  --max-retries "${MAX_RETRIES}" \
  --progress-every 1 \
  --deepseek-disable-thinking

"${PYTHON_BIN}" - "${OUTPUT_FILE}" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, encoding="utf-8") as handle:
    row = json.loads(handle.readline())

print(f"output={path}")
print(f"prompt_id={row.get('prompt_id')}")
print(f"kind={row.get('kind')}")
print(f"model={row.get('model')}")
print("")
print(row.get("text", ""))
PY

"${PYTHON_BIN}" scripts/local_prepare/validate_single_answer.py "${OUTPUT_FILE}"
