from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_remote_jobs(*, remote_project_dir: str) -> list[dict[str, Any]]:
    root = remote_project_dir.rstrip("/")
    return [
        _job(
            root,
            "data_prepare",
            "prompt_expansion",
            "configs/data_generation/questions.yaml",
            "python -m ttc_dense_verifier.cli build-questions --output data/raw_questions/questions.jsonl --limit 5000",
            ["data/raw_questions/questions.jsonl"],
        ),
        _job(
            root,
            "request_render",
            "negative_request_render",
            "configs/data_generation/negative_generation.yaml",
            'python -m ttc_dense_verifier.cli build-generation-requests --questions data/raw_questions/questions.jsonl --mode negative --model "${GENERATOR_MODEL:-Qwen2.5-32B-Instruct}" --output data/generated_negative/negative_generation_requests.jsonl',
            ["data/generated_negative/negative_generation_requests.jsonl"],
        ),
        _job(
            root,
            "answer_generation",
            "negative_answer_generation",
            "configs/data_generation/negative_generation.yaml",
            'python -m ttc_dense_verifier.cli run-generation-requests --input data/generated_negative/negative_generation_requests.jsonl --output data/generated_negative/negative_answers.jsonl --endpoint "${GENERATOR_ENDPOINT:?set GENERATOR_ENDPOINT}" --model "${GENERATOR_MODEL:-Qwen2.5-32B-Instruct}" --api-key "${MODEL_API_KEY:-}"',
            ["data/generated_negative/negative_answers.jsonl"],
        ),
        _job(
            root,
            "request_render",
            "positive_request_render",
            "configs/data_generation/positive_generation.yaml",
            'python -m ttc_dense_verifier.cli build-generation-requests --questions data/raw_questions/questions.jsonl --mode positive --model "${GENERATOR_MODEL:-Qwen2.5-32B-Instruct}" --output data/generated_positive/positive_generation_requests.jsonl',
            ["data/generated_positive/positive_generation_requests.jsonl"],
        ),
        _job(
            root,
            "answer_generation",
            "positive_answer_generation",
            "configs/data_generation/positive_generation.yaml",
            'python -m ttc_dense_verifier.cli run-generation-requests --input data/generated_positive/positive_generation_requests.jsonl --output data/generated_positive/positive_answers.jsonl --endpoint "${GENERATOR_ENDPOINT:?set GENERATOR_ENDPOINT}" --model "${GENERATOR_MODEL:-Qwen2.5-32B-Instruct}" --api-key "${MODEL_API_KEY:-}"',
            ["data/generated_positive/positive_answers.jsonl"],
        ),
        _job(
            root,
            "preference_split",
            "preference_split_export",
            "configs/data_generation/questions.yaml",
            "python -m ttc_dense_verifier.cli prepare-preferences --questions data/raw_questions/questions.jsonl --positive data/generated_positive/positive_answers.jsonl --negative data/generated_negative/negative_answers.jsonl --output-dir data/preference",
            [
                "data/preference/train_preference.jsonl",
                "data/preference/val_preference.jsonl",
                "data/preference/test_prompts.jsonl",
                "data/preference/data_report.md",
            ],
        ),
        _job(
            root,
            "dataset_export",
            "rm_dataset_export",
            "configs/training/verifier_rm_qwen7b.yaml",
            "python -m ttc_dense_verifier.cli export-rm-dataset --train data/preference/train_preference.jsonl --val data/preference/val_preference.jsonl --output-dir data/training/rm --dataset-name ttc_rm",
            ["data/training/rm/train_rm.jsonl", "data/training/rm/val_rm.jsonl", "data/training/rm/dataset_info.json"],
        ),
        _job(
            root,
            "dataset_export",
            "sft_dataset_export",
            "configs/training/generator_sft_qwen32b_lora.yaml",
            "python -m ttc_dense_verifier.cli export-sft-dataset --input data/preference/train_preference.jsonl --output data/training/sft/train_sft.jsonl",
            ["data/training/sft/train_sft.jsonl", "data/training/sft/dataset_info.json"],
        ),
        _job(
            root,
            "training_validation",
            "training_input_validation",
            "configs/training/verifier_rm_qwen7b.yaml",
            "python -m ttc_dense_verifier.cli validate-training-inputs --rm-config configs/training/verifier_rm_qwen7b.yaml --sft-config configs/training/generator_sft_qwen32b_lora.yaml --rm-dataset-dir data/training/rm --sft-dataset-dir data/training/sft --output outputs/logs/training_input_validation_${TTC_RUN_ID}.json",
            ["outputs/logs/training_input_validation_${TTC_RUN_ID}.json"],
        ),
        _job(
            root,
            "training",
            "verifier_rm_training",
            "configs/training/verifier_rm_qwen7b.yaml",
            "llamafactory-cli train configs/training/verifier_rm_qwen7b.yaml && python -m ttc_dense_verifier.cli export-training-summary --config configs/training/verifier_rm_qwen7b.yaml --output outputs/logs/verifier_rm_metrics_${TTC_RUN_ID}.json --label verifier_rm",
            ["checkpoints/verifier_qwen7b_rm", "outputs/logs/verifier_rm_metrics_${TTC_RUN_ID}.json"],
        ),
        _job(
            root,
            "training",
            "generator_sft_lora_training",
            "configs/training/generator_sft_qwen32b_lora.yaml",
            "llamafactory-cli train configs/training/generator_sft_qwen32b_lora.yaml && python -m ttc_dense_verifier.cli export-training-summary --config configs/training/generator_sft_qwen32b_lora.yaml --output outputs/logs/generator_sft_metrics_${TTC_RUN_ID}.json --label generator_sft",
            ["checkpoints/generator_qwen32b_sft_lora", "outputs/logs/generator_sft_metrics_${TTC_RUN_ID}.json"],
        ),
        _job(
            root,
            "service_switch",
            "trained_verifier_service_switch",
            "configs/inference/verifier_qwen7b.yaml",
            'bash scripts/remote_deploy/generated/switch_verifier_to_trained.sh && sleep "${SERVICE_STARTUP_SECONDS:-30}" && python -m ttc_dense_verifier.cli probe-remote-services --generator-endpoint "${GENERATOR_ENDPOINT:?set GENERATOR_ENDPOINT}" --generator-model "${GENERATOR_MODEL:-Qwen2.5-32B-Instruct}" --verifier-endpoint "${VERIFIER_ENDPOINT:?set VERIFIER_ENDPOINT}" --api-key "${MODEL_API_KEY:-}" --timeout-seconds "${HEALTH_TIMEOUT_SECONDS:-30}" --output outputs/logs/trained_verifier_probe_${TTC_RUN_ID}.json',
            ["outputs/logs/trained_verifier_probe_${TTC_RUN_ID}.json"],
        ),
        _job(
            root,
            "post_training_validation",
            "verifier_validation_scoring",
            "configs/training/verifier_rm_qwen7b.yaml",
            'python -m ttc_dense_verifier.cli score-preferences --input data/preference/val_preference.jsonl --output outputs/logs/verifier_validation_scores_${TTC_RUN_ID}.jsonl --endpoint "${VERIFIER_ENDPOINT:?set VERIFIER_ENDPOINT}" --api-key "${MODEL_API_KEY:-}"',
            ["outputs/logs/verifier_validation_scores_${TTC_RUN_ID}.jsonl"],
        ),
        _job(
            root,
            "post_training_validation",
            "verifier_score_validation",
            "configs/training/verifier_rm_qwen7b.yaml",
            'python -m ttc_dense_verifier.cli validate-verifier-scores --input outputs/logs/verifier_validation_scores_${TTC_RUN_ID}.jsonl --output outputs/logs/verifier_score_validation_${TTC_RUN_ID}.json --min-pairwise-accuracy "${MIN_VERIFIER_PAIRWISE_ACCURACY:-0.65}"',
            ["outputs/logs/verifier_score_validation_${TTC_RUN_ID}.json"],
        ),
        _job(
            root,
            "inference",
            "ttc_beam_inference",
            "configs/inference/beam_search_ttc.yaml",
            'python -m ttc_dense_verifier.cli decode-ttc --prompts data/preference/test_prompts.jsonl --output outputs/demo_cases/ttc_beam_outputs.jsonl --method beam --generator-endpoint "${GENERATOR_ENDPOINT:?set GENERATOR_ENDPOINT}" --verifier-endpoint "${VERIFIER_ENDPOINT:?set VERIFIER_ENDPOINT}" --generator-model "${GENERATOR_MODEL:-Qwen2.5-32B-Instruct}" --verifier-model "${VERIFIER_MODEL:-Qwen2.5-7B-RM}" --api-key "${MODEL_API_KEY:-}"',
            ["outputs/demo_cases/ttc_beam_outputs.jsonl"],
        ),
        _job(
            root,
            "inference",
            "ttc_mcts_inference",
            "configs/inference/mcts_ttc.yaml",
            'python -m ttc_dense_verifier.cli decode-ttc --prompts data/preference/test_prompts.jsonl --output outputs/demo_cases/ttc_mcts_outputs.jsonl --method mcts --generator-endpoint "${GENERATOR_ENDPOINT:?set GENERATOR_ENDPOINT}" --verifier-endpoint "${VERIFIER_ENDPOINT:?set VERIFIER_ENDPOINT}" --generator-model "${GENERATOR_MODEL:-Qwen2.5-32B-Instruct}" --verifier-model "${VERIFIER_MODEL:-Qwen2.5-7B-RM}" --api-key "${MODEL_API_KEY:-}"',
            ["outputs/demo_cases/ttc_mcts_outputs.jsonl"],
        ),
        _job(
            root,
            "evaluation",
            "evaluation_export",
            "configs/evaluation/metrics.yaml",
            'python -m ttc_dense_verifier.cli export-evaluation-assets --input outputs/demo_cases/ttc_beam_outputs.jsonl --output-dir outputs/tables/beam_eval --judge-model "${JUDGE_MODEL:-remote-judge-model}"',
            ["outputs/tables/beam_eval"],
        ),
    ]


def _job(
    root: str,
    phase: str,
    name: str,
    config_path: str,
    command: str,
    output_paths: list[str],
) -> dict[str, Any]:
    return {
        "name": name,
        "phase": phase,
        "config_path": config_path,
        "command": command,
        "log_path": f"{root}/outputs/logs/{name}_${{TTC_RUN_ID}}.log",
        "output_paths": output_paths,
        "execution_scope": "remote-only",
    }


def render_health_check_script(*, remote_project_dir: str) -> str:
    root = remote_project_dir.rstrip("/")
    return f"""#!/usr/bin/env bash
set -euo pipefail

cd "{root}"
export TTC_RUN_ID="${{TTC_RUN_ID:-health-$(date +%Y%m%d-%H%M%S)}}"
mkdir -p outputs/logs outputs/tables outputs/figures outputs/demo_cases
mkdir -p data/raw_questions data/generated_negative data/generated_positive data/preference data/evaluation_outputs data/training/rm data/training/sft
mkdir -p checkpoints/verifier_qwen7b_rm checkpoints/generator_qwen32b_sft_lora

echo "[health] project: {root}"
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
    raise SystemExit(f"PyTorch import failed: {{exc}}") from exc

if not torch.cuda.is_available():
    raise SystemExit("CUDA is not available to PyTorch")

for name in ("GENERATOR_ENDPOINT", "VERIFIER_ENDPOINT"):
    if not os.environ.get(name):
        raise SystemExit(f"{{name}} is required before remote generation or training checks")

print(f"cuda_device_count={{torch.cuda.device_count()}}")
print("endpoint variables present")
PY

echo "[health] writable directories"
test -w outputs/logs
test -w data/raw_questions
test -w checkpoints/verifier_qwen7b_rm

echo "[health] remote generator and verifier endpoints"
python -m ttc_dense_verifier.cli probe-remote-services \\
  --generator-endpoint "${{GENERATOR_ENDPOINT}}" \\
  --generator-model "${{GENERATOR_MODEL:-Qwen2.5-32B-Instruct}}" \\
  --verifier-endpoint "${{VERIFIER_ENDPOINT}}" \\
  --api-key "${{MODEL_API_KEY:-}}" \\
  --timeout-seconds "${{HEALTH_TIMEOUT_SECONDS:-30}}" \\
  --output "outputs/logs/remote_service_probe_${{TTC_RUN_ID}}.json"

echo "[health] remote-only runbook checks passed"
"""


def render_env_check_script(*, remote_project_dir: str) -> str:
    root = remote_project_dir.rstrip("/")
    return f"""#!/usr/bin/env bash
set -euo pipefail

cd "{root}"

if [ ! -f scripts/remote_deploy/generated/.env ]; then
  echo "[env] missing scripts/remote_deploy/generated/.env" >&2
  echo "[env] copy .env.example to .env and fill remote-specific values before health checks or long jobs" >&2
  exit 1
fi

set -a
source scripts/remote_deploy/generated/.env
set +a

require_nonempty() {{
  local name="$1"
  local value="${{!name:-}}"
  value="${{value%$'\\r'}}"
  if [ -z "${{value}}" ]; then
    echo "[env] required variable is empty: ${{name}}" >&2
    exit 1
  fi
}}

require_not_placeholder() {{
  local name="$1"
  local placeholder="$2"
  local value="${{!name:-}}"
  value="${{value%$'\\r'}}"
  if [ "${{value}}" = "${{placeholder}}" ]; then
    echo "[env] variable still uses placeholder value: ${{name}}=${{value}}" >&2
    exit 1
  fi
}}

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

GENERATOR_ENDPOINT="${{GENERATOR_ENDPOINT%$'\\r'}}"
VERIFIER_ENDPOINT="${{VERIFIER_ENDPOINT%$'\\r'}}"

case "${{GENERATOR_ENDPOINT}}" in
  http://*|https://*) ;;
  *) echo "[env] GENERATOR_ENDPOINT must be an http(s) URL" >&2; exit 1 ;;
esac

case "${{VERIFIER_ENDPOINT}}" in
  http://*|https://*) ;;
  *) echo "[env] VERIFIER_ENDPOINT must be an http(s) URL" >&2; exit 1 ;;
esac

echo "[env] remote environment configuration looks complete"
"""


def render_generator_service_script(*, remote_project_dir: str) -> str:
    root = remote_project_dir.rstrip("/")
    return f"""#!/usr/bin/env bash
set -euo pipefail

cd "{root}"
export TTC_RUN_ID="${{TTC_RUN_ID:-service-$(date +%Y%m%d-%H%M%S)}}"
export GENERATOR_PORT="${{GENERATOR_PORT:-8000}}"
export GENERATOR_HOST="${{GENERATOR_HOST:-0.0.0.0}}"
GENERATOR_ENDPOINT=http://127.0.0.1:${{GENERATOR_PORT}}/v1
export GENERATOR_ENDPOINT
mkdir -p outputs/logs

cat > outputs/logs/generator_service_${{TTC_RUN_ID}}.env <<SERVICE_ENV
GENERATOR_ENDPOINT=${{GENERATOR_ENDPOINT}}
GENERATOR_MODEL=${{GENERATOR_MODEL:-Qwen2.5-32B-Instruct}}
GENERATOR_MODEL_PATH=${{GENERATOR_MODEL_PATH:?set GENERATOR_MODEL_PATH}}
GENERATOR_PORT=${{GENERATOR_PORT}}
GENERATOR_TENSOR_PARALLEL_SIZE=${{GENERATOR_TENSOR_PARALLEL_SIZE:-6}}
SERVICE_ENV

tmux kill-session -t ttc_generator_service 2>/dev/null || true
tmux new-session -d -s ttc_generator_service "cd \\"{root}\\"; CUDA_VISIBLE_DEVICES=\\"${{GENERATOR_CUDA_VISIBLE_DEVICES:-0,1,2,3,4,5}}\\" vllm serve \\"${{GENERATOR_MODEL_PATH:?set GENERATOR_MODEL_PATH}}\\" --served-model-name \\"${{GENERATOR_MODEL:-Qwen2.5-32B-Instruct}}\\" --host \\"${{GENERATOR_HOST}}\\" --port \\"${{GENERATOR_PORT}}\\" --tensor-parallel-size \\"${{GENERATOR_TENSOR_PARALLEL_SIZE:-6}}\\" > \\"outputs/logs/generator_service_${{TTC_RUN_ID}}.log\\" 2>&1"

echo "GENERATOR_ENDPOINT=${{GENERATOR_ENDPOINT}}"
echo "[service] generator logs: outputs/logs/generator_service_${{TTC_RUN_ID}}.log"
"""


def render_verifier_service_script(*, remote_project_dir: str) -> str:
    root = remote_project_dir.rstrip("/")
    return f"""#!/usr/bin/env bash
set -euo pipefail

cd "{root}"
export TTC_RUN_ID="${{TTC_RUN_ID:-service-$(date +%Y%m%d-%H%M%S)}}"
export VERIFIER_PORT="${{VERIFIER_PORT:-8001}}"
export VERIFIER_HOST="${{VERIFIER_HOST:-0.0.0.0}}"
export VERIFIER_CHECKPOINT_DIR="${{VERIFIER_CHECKPOINT_DIR:-checkpoints/verifier_qwen7b_rm}}"
VERIFIER_ENDPOINT=http://127.0.0.1:${{VERIFIER_PORT}}/score
export VERIFIER_ENDPOINT
mkdir -p outputs/logs

cat > outputs/logs/verifier_service_${{TTC_RUN_ID}}.env <<SERVICE_ENV
VERIFIER_ENDPOINT=${{VERIFIER_ENDPOINT}}
VERIFIER_MODEL=${{VERIFIER_MODEL:-Qwen2.5-7B-RM}}
VERIFIER_CHECKPOINT_DIR=${{VERIFIER_CHECKPOINT_DIR}}
VERIFIER_PORT=${{VERIFIER_PORT}}
SERVICE_ENV

tmux kill-session -t ttc_verifier_service 2>/dev/null || true
tmux new-session -d -s ttc_verifier_service "cd \\"{root}\\"; export VERIFIER_HOST=\\"${{VERIFIER_HOST}}\\"; export VERIFIER_PORT=\\"${{VERIFIER_PORT}}\\"; export VERIFIER_CHECKPOINT_DIR=\\"${{VERIFIER_CHECKPOINT_DIR}}\\"; export CUDA_VISIBLE_DEVICES=\\"${{VERIFIER_CUDA_VISIBLE_DEVICES:-6,7}}\\"; ${{VERIFIER_SERVICE_COMMAND:?set VERIFIER_SERVICE_COMMAND}} > \\"outputs/logs/verifier_service_${{TTC_RUN_ID}}.log\\" 2>&1"

echo "VERIFIER_ENDPOINT=${{VERIFIER_ENDPOINT}}"
echo "[service] verifier logs: outputs/logs/verifier_service_${{TTC_RUN_ID}}.log"
"""


def render_switch_verifier_script(*, remote_project_dir: str) -> str:
    root = remote_project_dir.rstrip("/")
    return f"""#!/usr/bin/env bash
set -euo pipefail

cd "{root}"
export VERIFIER_CHECKPOINT_DIR="${{VERIFIER_CHECKPOINT_DIR:-checkpoints/verifier_qwen7b_rm}}"
echo "[service] switching verifier to ${{VERIFIER_CHECKPOINT_DIR}}"
bash scripts/remote_deploy/generated/start_verifier_service.sh
"""


def render_runbook_script(jobs: list[dict[str, Any]], *, remote_project_dir: str) -> str:
    root = remote_project_dir.rstrip("/")
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        f'PROJECT_DIR="{root}"',
        f'cd "{root}"',
        'export TTC_RUN_ID="${TTC_RUN_ID:-$(date +%Y%m%d-%H%M%S)}"',
        "mkdir -p outputs/logs",
        'echo "[runbook] remote-only execution plan ${TTC_RUN_ID}"',
        "",
        "wait_for_session() {",
        '  local session_name="$1"',
        '  while tmux has-session -t "${session_name}" 2>/dev/null; do',
        "    sleep 30",
        "  done",
        "}",
        "",
        "require_outputs() {",
        '  local missing=0',
        '  for output_path in "$@"; do',
        '    if [ ! -e "${output_path}" ]; then',
        '      echo "[runbook] missing expected output: ${output_path}" >&2',
        "      missing=1",
        "    fi",
        "  done",
        '  if [ "${missing}" -ne 0 ]; then',
        "    return 1",
        "  fi",
        "}",
        "",
        "launch_job() {",
        '  local name="$1"',
        '  local config_path="$2"',
        '  local command="$3"',
        '  local log_path="$4"',
        "  shift 4",
        '  local session_name="ttc_${name}"',
        '  local status_path="outputs/logs/${name}_${TTC_RUN_ID}.status"',
        '  local job_script="outputs/logs/${name}_${TTC_RUN_ID}.sh"',
        '  local config_copy_path="outputs/logs/${name}_${TTC_RUN_ID}.config"',
        '  local outputs_manifest_path="outputs/logs/${name}_${TTC_RUN_ID}.outputs"',
        '  local failure_path="outputs/logs/${name}_${TTC_RUN_ID}.failure"',
        '  rm -f "${status_path}" "${failure_path}"',
        '  if [ -f "${config_path}" ]; then',
        '    cp "${config_path}" "${config_copy_path}"',
        "  else",
        '    echo "missing config: ${config_path}" > "${config_copy_path}"',
        "  fi",
        '  printf "%s\\n" "$@" > "${outputs_manifest_path}"',
        '  cat > "${job_script}" <<JOB_SCRIPT',
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        'cd "${PROJECT_DIR}"',
        'echo "config=${config_path}"',
        '${command}',
        "JOB_SCRIPT",
        '  chmod +x "${job_script}"',
        '  echo "[runbook] launching ${name} with ${config_path}"',
        '  tmux new-session -d -s "${session_name}" "bash \\"${job_script}\\" > \\"${log_path}\\" 2>&1; echo \\\\$? > \\"${status_path}\\""',
        '  wait_for_session "${session_name}"',
        '  local status',
        '  status="$(cat "${status_path}")"',
        '  if [ "${status}" -ne 0 ]; then',
        '    echo "status=${status}" > "${failure_path}"',
        '    echo "log_path=${log_path}" >> "${failure_path}"',
        '    echo "config_path=${config_path}" >> "${failure_path}"',
        '    echo "[runbook] ${name} failed with status ${status}; see ${log_path}" >&2',
        "    return 1",
        "  fi",
        '  if ! require_outputs "$@"; then',
        '    echo "status=missing_outputs" > "${failure_path}"',
        '    echo "log_path=${log_path}" >> "${failure_path}"',
        '    echo "config_path=${config_path}" >> "${failure_path}"',
        "    return 1",
        "  fi",
        '  echo "[runbook] completed ${name}"',
        "}",
        "",
        "run_phase() {",
        '  local phase="$1"',
        '  echo "[runbook] phase: ${phase}"',
        "}",
        "",
    ]
    for phase in _ordered_phases(jobs):
        lines.append(f'run_phase "{phase}"')
        for job in [item for item in jobs if item.get("phase") == phase]:
            name = str(job["name"])
            command = str(job["command"])
            log_path = str(job["log_path"])
            config_path = str(job["config_path"])
            outputs = " ".join(_shell_quote_expand_run_id(str(output)) for output in job["output_paths"])
            lines.append(f"# tmux new-session -d -s ttc_{name}")
            lines.append(
                " ".join(
                    [
                        "launch_job",
                        _shell_quote(name),
                        _shell_quote(config_path),
                        _shell_quote(command),
                        _shell_quote_expand_run_id(log_path),
                        outputs,
                    ]
                ).rstrip()
            )
        lines.append("")
    lines.append('echo "[runbook] completed all remote-only phases"')
    return "\n".join(lines) + "\n"


def _ordered_phases(jobs: list[dict[str, Any]]) -> list[str]:
    preferred = [
        "data_prepare",
        "request_render",
        "answer_generation",
        "preference_split",
        "dataset_export",
        "training_validation",
        "training",
        "service_switch",
        "post_training_validation",
        "inference",
        "evaluation",
    ]
    present = {str(job.get("phase", "")) for job in jobs}
    return [phase for phase in preferred if phase in present] + sorted(present - set(preferred))


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _shell_quote_expand_run_id(value: str) -> str:
    if "${TTC_RUN_ID}" not in value:
        return _shell_quote(value)
    return '"' + value.replace('"', '\\"') + '"'


def render_env_example() -> str:
    return "\n".join(
        [
            "# Copy to .env on the remote server, then adjust values before running generated scripts.",
            "TTC_RUN_ID=",
            "GENERATOR_ENDPOINT=http://127.0.0.1:8000/v1",
            "VERIFIER_ENDPOINT=http://127.0.0.1:8001/score",
            "GENERATOR_MODEL=Qwen2.5-32B-Instruct",
            "VERIFIER_MODEL=Qwen2.5-7B-RM",
            "GENERATOR_MODEL_PATH=/models/Qwen2.5-32B-Instruct",
            "GENERATOR_PORT=8000",
            "GENERATOR_HOST=0.0.0.0",
            "GENERATOR_CUDA_VISIBLE_DEVICES=0,1,2,3,4,5",
            "GENERATOR_TENSOR_PARALLEL_SIZE=6",
            "VERIFIER_CHECKPOINT_DIR=checkpoints/verifier_qwen7b_rm",
            "VERIFIER_PORT=8001",
            "VERIFIER_HOST=0.0.0.0",
            "VERIFIER_CUDA_VISIBLE_DEVICES=6,7",
            "VERIFIER_SERVICE_COMMAND=",
            "JUDGE_MODEL=remote-judge-model",
            "MODEL_API_KEY=",
            "HEALTH_TIMEOUT_SECONDS=30",
            "SERVICE_STARTUP_SECONDS=30",
            "MIN_VERIFIER_PAIRWISE_ACCURACY=0.65",
            "",
        ]
    )


def render_deployment_notes(*, remote_project_dir: str) -> str:
    root = remote_project_dir.rstrip("/")
    return "\n".join(
        [
            "# Remote Deployment Runbook",
            "",
            f"Remote project directory: `{root}`",
            "",
            "1. Sync the repository contents to the remote project directory.",
            "2. Create and activate a Python environment with CUDA PyTorch, vLLM, LLaMA-Factory, tmux, and this package installed.",
            "3. Copy `.env.example` to `.env`, fill endpoint values, then run `set -a; source .env; set +a`.",
            "4. Run `bash scripts/remote_deploy/generated/env_check.sh` before starting services.",
            "5. Start generator serving with `bash scripts/remote_deploy/generated/start_generator_vllm.sh`.",
            "6. Start the current verifier service with `bash scripts/remote_deploy/generated/start_verifier_service.sh`.",
            "7. Run `bash scripts/remote_deploy/generated/health_check.sh` before any long job.",
            "8. Start the ordered workflow with `bash scripts/remote_deploy/generated/run_remote_jobs.sh` inside a persistent shell or tmux session.",
            "9. Inspect `outputs/logs/*_${TTC_RUN_ID}.log` and `outputs/logs/*_${TTC_RUN_ID}.status` after each phase.",
            "10. After verifier training, the runbook automatically runs `switch_verifier_to_trained.sh` and probes the trained verifier before score validation.",
            "",
            "The generated runbook never downloads model checkpoints locally. Model serving and cache warming must be handled on the remote server.",
            "",
        ]
    )


def _deprecated_parallel_runbook_body() -> str:
    return ""


def write_remote_runbook(output_dir: str | Path, *, remote_project_dir: str) -> None:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    jobs = build_remote_jobs(remote_project_dir=remote_project_dir)
    manifest = {
        "remote_project_dir": remote_project_dir.rstrip("/"),
        "jobs": jobs,
    }
    (target / "remote_jobs.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (target / "health_check.sh").write_text(
        render_health_check_script(remote_project_dir=remote_project_dir),
        encoding="utf-8",
    )
    (target / "env_check.sh").write_text(
        render_env_check_script(remote_project_dir=remote_project_dir),
        encoding="utf-8",
    )
    (target / "start_generator_vllm.sh").write_text(
        render_generator_service_script(remote_project_dir=remote_project_dir),
        encoding="utf-8",
    )
    (target / "start_verifier_service.sh").write_text(
        render_verifier_service_script(remote_project_dir=remote_project_dir),
        encoding="utf-8",
    )
    (target / "switch_verifier_to_trained.sh").write_text(
        render_switch_verifier_script(remote_project_dir=remote_project_dir),
        encoding="utf-8",
    )
    (target / "run_remote_jobs.sh").write_text(
        render_runbook_script(jobs, remote_project_dir=remote_project_dir),
        encoding="utf-8",
    )
    (target / ".env.example").write_text(render_env_example(), encoding="utf-8")
    (target / "DEPLOYMENT.md").write_text(
        render_deployment_notes(remote_project_dir=remote_project_dir),
        encoding="utf-8",
    )
