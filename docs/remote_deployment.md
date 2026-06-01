# Remote Deployment Notes

The repository does not download model checkpoints locally. Remote deployment should run on a Linux server with CUDA, enough disk for Qwen checkpoints, and enough GPUs for the selected tensor-parallel layout.

Recommended placement for the full workflow:

- GPUs 0-5: Qwen2.5-32B-Instruct generator served through vLLM.
- GPUs 6-7: Qwen2.5-7B verifier or reward model service.

Before long jobs, record GPU visibility, free VRAM, model service readiness, one generator request, one verifier request, dataset parse success, and writable output directories.

## Deployment Gate

The folder is ready to upload for a remote smoke check when these local checks pass:

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
rg -n "<model-download-keyword-regex>" README.md docs configs scripts src .gitignore
```

The folder is ready to start long training only after the remote machine passes:

```bash
set -a
source scripts/remote_deploy/generated/.env
set +a
bash scripts/remote_deploy/generated/health_check.sh
```

`health_check.sh` intentionally fails when `tmux`, `llamafactory-cli`, CUDA PyTorch, `GENERATOR_ENDPOINT`, `VERIFIER_ENDPOINT`, or a tiny generator/verifier probe request is unavailable. Set `GENERATOR_ENDPOINT` to the OpenAI-compatible base URL, for example `http://127.0.0.1:8000/v1`; the client appends the chat-completions route itself.

After verifier training, the generated runbook scores the validation preference split through `VERIFIER_ENDPOINT` and rejects the run unless `validate-verifier-scores` meets `MIN_VERIFIER_PAIRWISE_ACCURACY`, which defaults to `0.65`. Before the `post_training_validation` phase reaches `verifier_validation_scoring`, make sure `VERIFIER_ENDPOINT` serves the newly trained verifier checkpoint.

Each LLaMA-Factory training job also runs `export-training-summary` after `llamafactory-cli train`. The summary reads `trainer_state.json`, records the best metric, global step, last train/eval losses, and writes a stable `outputs/logs/*_metrics_${TTC_RUN_ID}.json` file for the runbook gate.

Every long-running job writes a timestamped log, a `.config` copy of the config path used, a `.outputs` manifest of expected artifacts, a `.status` exit-code file, and a `.failure` file when the command fails or expected outputs are missing.

## Ordered Remote Workflow

Generate the deployment scripts locally:

```bash
python -m ttc_dense_verifier.cli export-remote-runbook \
  --output-dir scripts/remote_deploy/generated \
  --remote-project-dir /data/lry_machine_learning/ttc_dense_verifier
```

Then copy the repository to the remote server and run:

```bash
make remote-sync
ssh g3
cd /data/lry_machine_learning/ttc_dense_verifier
cp scripts/remote_deploy/generated/.env.example scripts/remote_deploy/generated/.env
# Edit endpoint, model path, GPU, and verifier service values before sourcing.
bash scripts/remote_deploy/generated/env_check.sh
set -a
source scripts/remote_deploy/generated/.env
set +a
bash scripts/remote_deploy/generated/start_generator_vllm.sh
bash scripts/remote_deploy/generated/start_verifier_service.sh
bash scripts/remote_deploy/generated/health_check.sh
bash scripts/remote_deploy/generated/run_remote_jobs.sh
```

`start_generator_vllm.sh` starts the Qwen2.5-32B generator behind a vLLM OpenAI-compatible API. `start_verifier_service.sh` starts the current verifier score endpoint using `VERIFIER_SERVICE_COMMAND`; set that command to the reward-model HTTP server used on the remote machine. After verifier training finishes, the generated runbook runs `switch_verifier_to_trained.sh`, waits `SERVICE_STARTUP_SECONDS`, and probes the trained verifier before post-training validation and TTC inference.

The generated runbook executes phases in dependency order:

1. `data_prepare`
2. `request_render`
3. `answer_generation`
4. `preference_split`
5. `dataset_export`
6. `training_validation`
7. `training`
8. `service_switch`
9. `post_training_validation`
10. `inference`
11. `evaluation`

Each job runs under tmux, waits for completion, records a status file, and checks expected output paths before the next job starts. Logs are written under `outputs/logs/*_${TTC_RUN_ID}.log`.
