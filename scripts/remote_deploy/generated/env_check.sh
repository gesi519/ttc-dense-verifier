#!/usr/bin/env bash
set -euo pipefail

cd "/data/lry_machine_learning/ttc_dense_verifier"

if [ ! -f scripts/remote_deploy/generated/.env ]; then
  echo "[env] missing scripts/remote_deploy/generated/.env" >&2
  echo "[env] copy .env.example to .env and fill remote-specific values before health checks or long jobs" >&2
  exit 1
fi

set -a
source scripts/remote_deploy/generated/.env
set +a

require_nonempty() {
  local name="$1"
  local value="${!name:-}"
  if [ -z "${value}" ]; then
    echo "[env] required variable is empty: ${name}" >&2
    exit 1
  fi
}

require_not_placeholder() {
  local name="$1"
  local placeholder="$2"
  local value="${!name:-}"
  if [ "${value}" = "${placeholder}" ]; then
    echo "[env] variable still uses placeholder value: ${name}=${value}" >&2
    exit 1
  fi
}

require_nonempty GENERATOR_ENDPOINT
require_nonempty VERIFIER_ENDPOINT
require_nonempty GENERATOR_MODEL
require_nonempty VERIFIER_MODEL
require_nonempty GENERATOR_MODEL_PATH
require_nonempty VERIFIER_CHECKPOINT_DIR
require_nonempty VERIFIER_SERVICE_COMMAND
require_nonempty HEALTH_TIMEOUT_SECONDS
require_nonempty SERVICE_STARTUP_SECONDS
require_nonempty MIN_VERIFIER_PAIRWISE_ACCURACY

require_not_placeholder GENERATOR_MODEL_PATH /models/Qwen2.5-32B-Instruct
require_not_placeholder VERIFIER_SERVICE_COMMAND ""

case "${GENERATOR_ENDPOINT}" in
  http://*|https://*) ;;
  *) echo "[env] GENERATOR_ENDPOINT must be an http(s) URL" >&2; exit 1 ;;
esac

case "${VERIFIER_ENDPOINT}" in
  http://*|https://*) ;;
  *) echo "[env] VERIFIER_ENDPOINT must be an http(s) URL" >&2; exit 1 ;;
esac

echo "[env] remote environment configuration looks complete"
