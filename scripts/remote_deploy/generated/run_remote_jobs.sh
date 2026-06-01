#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/data/lry_machine_learning/ttc_dense_verifier"
cd "/data/lry_machine_learning/ttc_dense_verifier"
export TTC_RUN_ID="${TTC_RUN_ID:-$(date +%Y%m%d-%H%M%S)}"
mkdir -p outputs/logs
echo "[runbook] remote-only execution plan ${TTC_RUN_ID}"

wait_for_session() {
  local session_name="$1"
  while tmux has-session -t "${session_name}" 2>/dev/null; do
    sleep 30
  done
}

require_outputs() {
  local missing=0
  for output_path in "$@"; do
    if [ ! -e "${output_path}" ]; then
      echo "[runbook] missing expected output: ${output_path}" >&2
      missing=1
    fi
  done
  if [ "${missing}" -ne 0 ]; then
    return 1
  fi
}

launch_job() {
  local name="$1"
  local config_path="$2"
  local command="$3"
  local log_path="$4"
  shift 4
  local session_name="ttc_${name}"
  local status_path="outputs/logs/${name}_${TTC_RUN_ID}.status"
  local job_script="outputs/logs/${name}_${TTC_RUN_ID}.sh"
  local config_copy_path="outputs/logs/${name}_${TTC_RUN_ID}.config"
  local outputs_manifest_path="outputs/logs/${name}_${TTC_RUN_ID}.outputs"
  local failure_path="outputs/logs/${name}_${TTC_RUN_ID}.failure"
  rm -f "${status_path}" "${failure_path}"
  if [ -f "${config_path}" ]; then
    cp "${config_path}" "${config_copy_path}"
  else
    echo "missing config: ${config_path}" > "${config_copy_path}"
  fi
  printf "%s\n" "$@" > "${outputs_manifest_path}"
  cat > "${job_script}" <<JOB_SCRIPT
#!/usr/bin/env bash
set -euo pipefail
cd "${PROJECT_DIR}"
echo "config=${config_path}"
${command}
JOB_SCRIPT
  chmod +x "${job_script}"
  echo "[runbook] launching ${name} with ${config_path}"
  tmux new-session -d -s "${session_name}" "bash \"${job_script}\" > \"${log_path}\" 2>&1; echo \\$? > \"${status_path}\""
  wait_for_session "${session_name}"
  local status
  status="$(cat "${status_path}")"
  if [ "${status}" -ne 0 ]; then
    echo "status=${status}" > "${failure_path}"
    echo "log_path=${log_path}" >> "${failure_path}"
    echo "config_path=${config_path}" >> "${failure_path}"
    echo "[runbook] ${name} failed with status ${status}; see ${log_path}" >&2
    return 1
  fi
  if ! require_outputs "$@"; then
    echo "status=missing_outputs" > "${failure_path}"
    echo "log_path=${log_path}" >> "${failure_path}"
    echo "config_path=${config_path}" >> "${failure_path}"
    return 1
  fi
  echo "[runbook] completed ${name}"
}

run_phase() {
  local phase="$1"
  echo "[runbook] phase: ${phase}"
}

run_phase "data_prepare"
# tmux new-session -d -s ttc_prompt_expansion
launch_job 'prompt_expansion' 'configs/data_generation/questions.yaml' 'python -m ttc_dense_verifier.cli build-questions --output data/raw_questions/questions.jsonl --limit 5000' "/data/lry_machine_learning/ttc_dense_verifier/outputs/logs/prompt_expansion_${TTC_RUN_ID}.log" 'data/raw_questions/questions.jsonl'

run_phase "request_render"
# tmux new-session -d -s ttc_negative_request_render
launch_job 'negative_request_render' 'configs/data_generation/negative_generation.yaml' 'python -m ttc_dense_verifier.cli build-generation-requests --questions data/raw_questions/questions.jsonl --mode negative --model "${GENERATOR_MODEL:-Qwen2.5-32B-Instruct}" --output data/generated_negative/negative_generation_requests.jsonl' "/data/lry_machine_learning/ttc_dense_verifier/outputs/logs/negative_request_render_${TTC_RUN_ID}.log" 'data/generated_negative/negative_generation_requests.jsonl'
# tmux new-session -d -s ttc_positive_request_render
launch_job 'positive_request_render' 'configs/data_generation/positive_generation.yaml' 'python -m ttc_dense_verifier.cli build-generation-requests --questions data/raw_questions/questions.jsonl --mode positive --model "${GENERATOR_MODEL:-Qwen2.5-32B-Instruct}" --output data/generated_positive/positive_generation_requests.jsonl' "/data/lry_machine_learning/ttc_dense_verifier/outputs/logs/positive_request_render_${TTC_RUN_ID}.log" 'data/generated_positive/positive_generation_requests.jsonl'

run_phase "answer_generation"
# tmux new-session -d -s ttc_negative_answer_generation
launch_job 'negative_answer_generation' 'configs/data_generation/negative_generation.yaml' 'python -m ttc_dense_verifier.cli run-generation-requests --input data/generated_negative/negative_generation_requests.jsonl --output data/generated_negative/negative_answers.jsonl --endpoint "${GENERATOR_ENDPOINT:?set GENERATOR_ENDPOINT}" --model "${GENERATOR_MODEL:-Qwen2.5-32B-Instruct}" --api-key "${MODEL_API_KEY:-}"' "/data/lry_machine_learning/ttc_dense_verifier/outputs/logs/negative_answer_generation_${TTC_RUN_ID}.log" 'data/generated_negative/negative_answers.jsonl'
# tmux new-session -d -s ttc_positive_answer_generation
launch_job 'positive_answer_generation' 'configs/data_generation/positive_generation.yaml' 'python -m ttc_dense_verifier.cli run-generation-requests --input data/generated_positive/positive_generation_requests.jsonl --output data/generated_positive/positive_answers.jsonl --endpoint "${GENERATOR_ENDPOINT:?set GENERATOR_ENDPOINT}" --model "${GENERATOR_MODEL:-Qwen2.5-32B-Instruct}" --api-key "${MODEL_API_KEY:-}"' "/data/lry_machine_learning/ttc_dense_verifier/outputs/logs/positive_answer_generation_${TTC_RUN_ID}.log" 'data/generated_positive/positive_answers.jsonl'

run_phase "preference_split"
# tmux new-session -d -s ttc_preference_split_export
launch_job 'preference_split_export' 'configs/data_generation/questions.yaml' 'python -m ttc_dense_verifier.cli prepare-preferences --questions data/raw_questions/questions.jsonl --positive data/generated_positive/positive_answers.jsonl --negative data/generated_negative/negative_answers.jsonl --output-dir data/preference' "/data/lry_machine_learning/ttc_dense_verifier/outputs/logs/preference_split_export_${TTC_RUN_ID}.log" 'data/preference/train_preference.jsonl' 'data/preference/val_preference.jsonl' 'data/preference/test_prompts.jsonl' 'data/preference/data_report.md'

run_phase "dataset_export"
# tmux new-session -d -s ttc_rm_dataset_export
launch_job 'rm_dataset_export' 'configs/training/verifier_rm_qwen7b.yaml' 'python -m ttc_dense_verifier.cli export-rm-dataset --train data/preference/train_preference.jsonl --val data/preference/val_preference.jsonl --output-dir data/training/rm --dataset-name ttc_rm' "/data/lry_machine_learning/ttc_dense_verifier/outputs/logs/rm_dataset_export_${TTC_RUN_ID}.log" 'data/training/rm/train_rm.jsonl' 'data/training/rm/val_rm.jsonl' 'data/training/rm/dataset_info.json'
# tmux new-session -d -s ttc_sft_dataset_export
launch_job 'sft_dataset_export' 'configs/training/generator_sft_qwen32b_lora.yaml' 'python -m ttc_dense_verifier.cli export-sft-dataset --input data/preference/train_preference.jsonl --output data/training/sft/train_sft.jsonl' "/data/lry_machine_learning/ttc_dense_verifier/outputs/logs/sft_dataset_export_${TTC_RUN_ID}.log" 'data/training/sft/train_sft.jsonl' 'data/training/sft/dataset_info.json'

run_phase "training_validation"
# tmux new-session -d -s ttc_training_input_validation
launch_job 'training_input_validation' 'configs/training/verifier_rm_qwen7b.yaml' 'python -m ttc_dense_verifier.cli validate-training-inputs --rm-config configs/training/verifier_rm_qwen7b.yaml --sft-config configs/training/generator_sft_qwen32b_lora.yaml --rm-dataset-dir data/training/rm --sft-dataset-dir data/training/sft --output outputs/logs/training_input_validation_${TTC_RUN_ID}.json' "/data/lry_machine_learning/ttc_dense_verifier/outputs/logs/training_input_validation_${TTC_RUN_ID}.log" "outputs/logs/training_input_validation_${TTC_RUN_ID}.json"

run_phase "training"
# tmux new-session -d -s ttc_verifier_rm_training
launch_job 'verifier_rm_training' 'configs/training/verifier_rm_qwen7b.yaml' 'llamafactory-cli train configs/training/verifier_rm_qwen7b.yaml && python -m ttc_dense_verifier.cli export-training-summary --config configs/training/verifier_rm_qwen7b.yaml --output outputs/logs/verifier_rm_metrics_${TTC_RUN_ID}.json --label verifier_rm' "/data/lry_machine_learning/ttc_dense_verifier/outputs/logs/verifier_rm_training_${TTC_RUN_ID}.log" 'checkpoints/verifier_qwen7b_rm' "outputs/logs/verifier_rm_metrics_${TTC_RUN_ID}.json"
# tmux new-session -d -s ttc_generator_sft_lora_training
launch_job 'generator_sft_lora_training' 'configs/training/generator_sft_qwen32b_lora.yaml' 'llamafactory-cli train configs/training/generator_sft_qwen32b_lora.yaml && python -m ttc_dense_verifier.cli export-training-summary --config configs/training/generator_sft_qwen32b_lora.yaml --output outputs/logs/generator_sft_metrics_${TTC_RUN_ID}.json --label generator_sft' "/data/lry_machine_learning/ttc_dense_verifier/outputs/logs/generator_sft_lora_training_${TTC_RUN_ID}.log" 'checkpoints/generator_qwen32b_sft_lora' "outputs/logs/generator_sft_metrics_${TTC_RUN_ID}.json"

run_phase "service_switch"
# tmux new-session -d -s ttc_trained_verifier_service_switch
launch_job 'trained_verifier_service_switch' 'configs/inference/verifier_qwen7b.yaml' 'bash scripts/remote_deploy/generated/switch_verifier_to_trained.sh && sleep "${SERVICE_STARTUP_SECONDS:-30}" && python -m ttc_dense_verifier.cli probe-remote-services --generator-endpoint "${GENERATOR_ENDPOINT:?set GENERATOR_ENDPOINT}" --generator-model "${GENERATOR_MODEL:-Qwen2.5-32B-Instruct}" --verifier-endpoint "${VERIFIER_ENDPOINT:?set VERIFIER_ENDPOINT}" --api-key "${MODEL_API_KEY:-}" --timeout-seconds "${HEALTH_TIMEOUT_SECONDS:-30}" --output outputs/logs/trained_verifier_probe_${TTC_RUN_ID}.json' "/data/lry_machine_learning/ttc_dense_verifier/outputs/logs/trained_verifier_service_switch_${TTC_RUN_ID}.log" "outputs/logs/trained_verifier_probe_${TTC_RUN_ID}.json"

run_phase "post_training_validation"
# tmux new-session -d -s ttc_verifier_validation_scoring
launch_job 'verifier_validation_scoring' 'configs/training/verifier_rm_qwen7b.yaml' 'python -m ttc_dense_verifier.cli score-preferences --input data/preference/val_preference.jsonl --output outputs/logs/verifier_validation_scores_${TTC_RUN_ID}.jsonl --endpoint "${VERIFIER_ENDPOINT:?set VERIFIER_ENDPOINT}" --api-key "${MODEL_API_KEY:-}"' "/data/lry_machine_learning/ttc_dense_verifier/outputs/logs/verifier_validation_scoring_${TTC_RUN_ID}.log" "outputs/logs/verifier_validation_scores_${TTC_RUN_ID}.jsonl"
# tmux new-session -d -s ttc_verifier_score_validation
launch_job 'verifier_score_validation' 'configs/training/verifier_rm_qwen7b.yaml' 'python -m ttc_dense_verifier.cli validate-verifier-scores --input outputs/logs/verifier_validation_scores_${TTC_RUN_ID}.jsonl --output outputs/logs/verifier_score_validation_${TTC_RUN_ID}.json --min-pairwise-accuracy "${MIN_VERIFIER_PAIRWISE_ACCURACY:-0.65}"' "/data/lry_machine_learning/ttc_dense_verifier/outputs/logs/verifier_score_validation_${TTC_RUN_ID}.log" "outputs/logs/verifier_score_validation_${TTC_RUN_ID}.json"

run_phase "inference"
# tmux new-session -d -s ttc_ttc_beam_inference
launch_job 'ttc_beam_inference' 'configs/inference/beam_search_ttc.yaml' 'python -m ttc_dense_verifier.cli decode-ttc --prompts data/preference/test_prompts.jsonl --output outputs/demo_cases/ttc_beam_outputs.jsonl --method beam --generator-endpoint "${GENERATOR_ENDPOINT:?set GENERATOR_ENDPOINT}" --verifier-endpoint "${VERIFIER_ENDPOINT:?set VERIFIER_ENDPOINT}" --generator-model "${GENERATOR_MODEL:-Qwen2.5-32B-Instruct}" --verifier-model "${VERIFIER_MODEL:-Qwen2.5-7B-RM}" --api-key "${MODEL_API_KEY:-}"' "/data/lry_machine_learning/ttc_dense_verifier/outputs/logs/ttc_beam_inference_${TTC_RUN_ID}.log" 'outputs/demo_cases/ttc_beam_outputs.jsonl'
# tmux new-session -d -s ttc_ttc_mcts_inference
launch_job 'ttc_mcts_inference' 'configs/inference/mcts_ttc.yaml' 'python -m ttc_dense_verifier.cli decode-ttc --prompts data/preference/test_prompts.jsonl --output outputs/demo_cases/ttc_mcts_outputs.jsonl --method mcts --generator-endpoint "${GENERATOR_ENDPOINT:?set GENERATOR_ENDPOINT}" --verifier-endpoint "${VERIFIER_ENDPOINT:?set VERIFIER_ENDPOINT}" --generator-model "${GENERATOR_MODEL:-Qwen2.5-32B-Instruct}" --verifier-model "${VERIFIER_MODEL:-Qwen2.5-7B-RM}" --api-key "${MODEL_API_KEY:-}"' "/data/lry_machine_learning/ttc_dense_verifier/outputs/logs/ttc_mcts_inference_${TTC_RUN_ID}.log" 'outputs/demo_cases/ttc_mcts_outputs.jsonl'

run_phase "evaluation"
# tmux new-session -d -s ttc_evaluation_export
launch_job 'evaluation_export' 'configs/evaluation/metrics.yaml' 'python -m ttc_dense_verifier.cli export-evaluation-assets --input outputs/demo_cases/ttc_beam_outputs.jsonl --output-dir outputs/tables/beam_eval --judge-model "${JUDGE_MODEL:-remote-judge-model}"' "/data/lry_machine_learning/ttc_dense_verifier/outputs/logs/evaluation_export_${TTC_RUN_ID}.log" 'outputs/tables/beam_eval'

echo "[runbook] completed all remote-only phases"
