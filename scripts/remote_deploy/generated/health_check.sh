#!/usr/bin/env bash
set -euo pipefail

cd "/srv/ttc-dense-verifier"
export TTC_RUN_ID="${TTC_RUN_ID:-health-$(date +%Y%m%d-%H%M%S)}"
mkdir -p outputs/logs outputs/tables outputs/figures outputs/demo_cases
mkdir -p data/raw_questions data/generated_negative data/generated_positive data/preference data/evaluation_outputs data/training/rm data/training/sft
mkdir -p checkpoints/verifier_qwen7b_rm checkpoints/generator_qwen32b_sft_lora

echo "[health] project: /srv/ttc-dense-verifier"
echo "[health] required commands"
command -v python >/dev/null
command -v tmux >/dev/null
command -v nvidia-smi >/dev/null
command -v vllm >/dev/null
command -v llamafactory-cli >/dev/null

echo "[health] gpu inventory"
nvidia-smi

echo "[health] python cli"
python -m ttc_dense_verifier.cli --help >/dev/null

echo "[health] python runtime and endpoint variables"
python - <<'PY'
import importlib.util
import os

if importlib.util.find_spec("ttc_dense_verifier") is None:
    raise SystemExit("ttc_dense_verifier package is not importable")

try:
    import torch
except Exception as exc:
    raise SystemExit(f"PyTorch import failed: {exc}") from exc

if not torch.cuda.is_available():
    raise SystemExit("CUDA is not available to PyTorch")

for name in ("GENERATOR_ENDPOINT", "VERIFIER_ENDPOINT"):
    if not os.environ.get(name):
        raise SystemExit(f"{name} is required before remote generation or training checks")

print(f"cuda_device_count={torch.cuda.device_count()}")
print("endpoint variables present")
PY

echo "[health] writable directories"
test -w outputs/logs
test -w data/raw_questions
test -w checkpoints/verifier_qwen7b_rm

echo "[health] remote generator and verifier endpoints"
python -m ttc_dense_verifier.cli probe-remote-services \
  --generator-endpoint "${GENERATOR_ENDPOINT}" \
  --generator-model "${GENERATOR_MODEL:-Qwen2.5-32B-Instruct}" \
  --verifier-endpoint "${VERIFIER_ENDPOINT}" \
  --api-key "${MODEL_API_KEY:-}" \
  --timeout-seconds "${HEALTH_TIMEOUT_SECONDS:-30}" \
  --output "outputs/logs/remote_service_probe_${TTC_RUN_ID}.json"

echo "[health] remote-only runbook checks passed"
