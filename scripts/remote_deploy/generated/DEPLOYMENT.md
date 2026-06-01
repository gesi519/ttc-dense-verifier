# Remote Deployment Runbook

Remote project directory: `/srv/ttc-dense-verifier`

1. Sync the repository contents to the remote project directory.
2. Create and activate a Python environment with CUDA PyTorch, vLLM, LLaMA-Factory, tmux, and this package installed.
3. Copy `.env.example` to `.env`, fill endpoint values, then run `set -a; source .env; set +a`.
4. Start generator serving with `bash scripts/remote_deploy/generated/start_generator_vllm.sh`.
5. Start the current verifier service with `bash scripts/remote_deploy/generated/start_verifier_service.sh`.
6. Run `bash scripts/remote_deploy/generated/health_check.sh` before any long job.
7. Start the ordered workflow with `bash scripts/remote_deploy/generated/run_remote_jobs.sh` inside a persistent shell or tmux session.
8. Inspect `outputs/logs/*_${TTC_RUN_ID}.log` and `outputs/logs/*_${TTC_RUN_ID}.status` after each phase.
9. After verifier training, the runbook automatically runs `switch_verifier_to_trained.sh` and probes the trained verifier before score validation.

The generated runbook never downloads model checkpoints locally. Model serving and cache warming must be handled on the remote server.
