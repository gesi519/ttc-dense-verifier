#!/usr/bin/env bash
set -euo pipefail

cd "/srv/ttc-dense-verifier"
export VERIFIER_CHECKPOINT_DIR="${VERIFIER_CHECKPOINT_DIR:-checkpoints/verifier_qwen7b_rm}"
echo "[service] switching verifier to ${VERIFIER_CHECKPOINT_DIR}"
bash scripts/remote_deploy/generated/start_verifier_service.sh
