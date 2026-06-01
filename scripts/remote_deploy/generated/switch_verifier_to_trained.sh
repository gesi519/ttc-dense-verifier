#!/usr/bin/env bash
set -euo pipefail

cd "/data/lry_machine_learning/ttc_dense_verifier"
export VERIFIER_CHECKPOINT_DIR="${VERIFIER_CHECKPOINT_DIR:-checkpoints/verifier_qwen7b_rm}"
echo "[service] switching verifier to ${VERIFIER_CHECKPOINT_DIR}"
bash scripts/remote_deploy/generated/start_verifier_service.sh
